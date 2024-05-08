import logging
import os
import random
import subprocess
import time
import traceback
import uuid

import docker
import yaml

from .db_utils import DBUtils
from .extensions import log
from .models import DynamicCheckChallenge, OwlContainers


def safe_quote(s: str, double=False):
    if double:
        return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'
    else:
        return "'" + s.replace("'", "'\"'\"'") + "'"


def resv_alnum(s: str):
    return "".join([c for c in s if c.isalnum()])


class DockerUtils:
    class SafeProtectError(Exception):
        pass

    client: docker.DockerClient = None

    @staticmethod
    def get_docker_client():
        configs = DBUtils.get_all_configs()
        if DockerUtils.client is not None:
            return DockerUtils.client
        else:
            DockerUtils.client = docker.DockerClient(
                base_url=configs.get("docker_api_url")
            )
            return DockerUtils.client

    @staticmethod
    def join_network(network_name, container_name):
        append_containers = (
            DBUtils.get_all_configs()
            .get("docker_auto_connect_containers", "")
            .split(",")
        )
        containers = [s.strip() for s in append_containers]
        containers.insert(0, container_name)
        if len(containers) <= 1:
            return
        client = DockerUtils.get_docker_client()
        if len(client.networks.list(names=[network_name])) > 0:
            DockerUtils.remove_network(network_name)
        network = client.networks.create(
            network_name,
            internal=True,
            attachable=True,
            driver="overlay",
            scope="swarm",
        )
        c_objs = client.containers.list(filters={"name": containers})
        for c in c_objs:
            if c.name in containers:
                network.connect(c)

    @staticmethod
    def remove_network(network_name):
        append_containers = (
            DBUtils.get_all_configs()
            .get("docker_auto_connect_containers", "")
            .split(",")
        )
        append_containers = [s.strip() for s in append_containers]
        client = DockerUtils.get_docker_client()
        network_list = client.networks.list(names=[network_name])
        if len(network_list) == 0:
            return
        network = network_list[0]
        c_objs = client.containers.list(filters={"name": append_containers})
        for c in c_objs:
            if c.name in append_containers:
                network.disconnect(c, force=True)
        network.remove()

    @staticmethod
    def get_name(user_id, challenge_id, category):
        return "ctfd-chall_user{}_challenge{}_{}".format(
            user_id, challenge_id, category
        ).lower()

    @staticmethod
    def get_container_id(container_name):
        client = DockerUtils.get_docker_client()
        container = client.containers.get(container_name)
        container_short_id = container.short_id
        return container_short_id

    @staticmethod
    def get_frp_http_container_name(name, docker_id):
        return name + "_" + docker_id

    @staticmethod
    def get_frp_http_network_name(docker_id):
        return "frp-http_{}".format(docker_id)

    @staticmethod
    def get_docker_id(name):
        # return str(uuid.uuid3(uuid.NAMESPACE_DNS, name)).replace("-", "")
        rnd_chars = "".join(random.choices("0123456789abcdef", k=6))
        return str(uuid.uuid3(uuid.NAMESPACE_DNS, name + "." + rnd_chars))

    @staticmethod
    def gen_flag():
        configs = DBUtils.get_all_configs()
        prefix = configs.get("docker_flag_prefix")
        flag = "{" + str(uuid.uuid4()) + "}"
        flag = prefix + flag  # .replace("-","")
        while OwlContainers.query.filter_by(flag=flag).first() is not None:
            flag = prefix + "{" + str(uuid.uuid4()) + "}"
        return flag

    @staticmethod
    def get_socket():
        configs = DBUtils.get_all_configs()
        socket = configs.get("docker_api_url")
        return socket

    @staticmethod
    def get_available_rnd_ports(range: tuple, count=1):
        if count <= 0:
            return []
        min_port, max_port = range
        all_container = DBUtils.get_all_container()
        black_ports_list = [_.port for _ in all_container]
        available_port_count = max_port - min_port + 1 - len(black_ports_list)
        if count > available_port_count:
            return []
        result = []
        max_fail_count = count + 10
        while len(result) < count and max_fail_count > 0:
            port = random.randint(min_port, max_port)
            if port not in black_ports_list:
                result.append(port)
                black_ports_list.append(port)
            else:
                max_fail_count -= 1
        if len(result) < count:
            port = min_port
            while len(result) < count and port <= max_port:
                if port not in black_ports_list:
                    result.append(port)
                    black_ports_list.append(port)
                port += 1
        return result

    @staticmethod
    def fmt_compose_file(
        content,
        pwd,
        local_image,
        port_range: tuple,
        frp_type,
        frp_http_container_name=None,
    ):
        """
        ### Description

        For FRP_TYPE is HTTP:
        - If it contains more than one service, add `container_name:<key_name>` to the service which exposes http subdomain port

        For FRP_TYPE is DIRECT:
        - Replace `<key_port>:port` to `<random_port>:port`, and remove other ports not in format of `<key_port>:port`

        ### The following is not implemented yet:

        if ports are like:
            - 1234:80
            - 1234:81
            - 82

        It will generates 2 random ports respectively for (80, 81) and (82)
        """
        conf = yaml.safe_load(content)

        """Safe Check"""
        # safe_fa_dir = os.path.realpath(os.environ['PROBLEM_DOCKER_RUN_FOLDER'])
        safe_fa_dir = os.path.realpath(pwd)
        for sv_name in conf["services"]:
            conf_sv = conf["services"][sv_name]
            # check safe volumes path
            if "volumes" in conf_sv:
                for i in range(len(conf_sv["volumes"])):
                    volume_arrays = conf_sv["volumes"][i].split(":")
                    if len(volume_arrays) > 3:
                        raise DockerUtils.SafeProtectError(
                            "Invalid volume path: {}".format(conf_sv["volumes"][i])
                        )
                    v_src_path = volume_arrays[0]
                    command = "cd {} && realpath {}".format(
                        safe_quote(pwd), safe_quote(v_src_path, True)
                    )
                    v_src_realpath = (
                        subprocess.run(
                            command,
                            shell=True,
                            check=True,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                        )
                        .stdout.decode()
                        .strip()
                    )
                    # contains '\n'
                    if v_src_realpath.find("\n") != -1:
                        raise DockerUtils.SafeProtectError(
                            "Invalid volume source path: {}".format(v_src_path)
                        )
                    # not start with safe_fa_dir
                    if not v_src_realpath.startswith(safe_fa_dir):
                        raise DockerUtils.SafeProtectError(
                            "Volume source path not in safe folder: {}".format(
                                v_src_path
                            )
                        )
            # check env_file
            if "env_file" in conf_sv:
                for i in range(len(conf_sv["env_file"])):
                    env_file_path = conf_sv["env_file"][i]
                    command = "cd {} && realpath {}".format(
                        safe_quote(pwd), safe_quote(env_file_path, True)
                    )
                    env_file_realpath = (
                        subprocess.run(
                            command,
                            shell=True,
                            check=True,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                        )
                        .stdout.decode()
                        .strip()
                    )
                    # contains '\n'
                    if env_file_realpath.find("\n") != -1:
                        raise DockerUtils.SafeProtectError(
                            "Invalid env_file path: {}".format(env_file_path)
                        )
                    # not start with safe_fa_dir
                    if not env_file_realpath.startswith(safe_fa_dir):
                        raise DockerUtils.SafeProtectError(
                            "The env_file not in safe folder: {}".format(env_file_path)
                        )

        """Image Name When Local Build"""
        for sv_name in conf["services"]:
            conf_sv = conf["services"][sv_name]
            if "build" in conf_sv and "image" not in conf_sv:
                conf_sv["image"] = (
                    local_image[0] + "_" + resv_alnum(sv_name) + ":" + local_image[1]
                )

        """Port Assign"""
        # # check and collect ports
        # port_assign_map = {
        #     "unknown_cnt": 0
        # }
        # for sv_name in conf['services']:
        #     conf_sv = conf['services'][sv_name]
        #     if 'ports' in conf_sv:
        #         for i in range(len(conf_sv['ports'])):
        #             port_arrays = conf_sv['ports'][i].split(":")
        #             if len(port_arrays) > 2:
        #                 raise DockerUtils.SafeProtectError("Invalid port format: {}".format(conf_sv['ports'][i]))
        #             if len(port_arrays) == 1:
        #                 port_assign_map["unknown_cnt"] += 1
        #             else:
        #                 port_assign_map[port_arrays[0]] = 0
        # tot_port_count = len(port_assign_map.keys) - 1 + port_assign_map["unknown_cnt"]
        # collected_ports = DockerUtils.get_available_rnd_ports(port_range, tot_port_count)
        # if len(collected_ports) != tot_port_count:
        #     raise DockerUtils.SafeProtectError("No available ports")
        # del port_assign_map["unknown_cnt"]
        # for k, v in port_assign_map.items():
        #     port_assign_map[k] = collected_ports.pop()
        # port_assign_map["unknown"] = collected_ports
        # # assign ports
        # for sv_name in conf['services']:
        #     conf_sv = conf['services'][sv_name]
        #     if 'ports' in conf_sv:
        #         conf_sv_p = conf_sv['ports']
        #         for i in range(len(conf_sv_p)):
        #             port_arrays = conf_sv_p[i].split(":")
        #             if len(port_arrays) == 1:
        #                 conf_sv_p[i] = port_assign_map["unknown"].pop() + ":" + port_arrays[0]
        #             else :
        #                 conf_sv_p[i] = port_assign_map[port_arrays[0]] + ":" + port_arrays[1]

        # assign ports
        KEY_PORT = 9999
        KEY_NAME = "frp-http"
        port_assigned = 0
        # frp type: http
        if frp_type.upper() == "HTTP":
            for sv_name in conf["services"]:
                conf_sv = conf["services"][sv_name]
                if "ports" in conf_sv:
                    # remove each port reflection
                    new_sv_p = []
                    for p in conf_sv["ports"]:
                        new_sv_p.append(str(p).split(":")[-1])
                    conf_sv["ports"] = new_sv_p
                if "container_name" in conf_sv:
                    if (
                        conf_sv["container_name"] == KEY_NAME
                        and frp_http_container_name is not None
                    ):
                        conf_sv["container_name"] = frp_http_container_name
            if (
                len(conf["services"].keys()) == 1
                and frp_http_container_name is not None
            ):
                sv_name = list(conf["services"].keys())[0]
                conf["services"][sv_name]["container_name"] = frp_http_container_name
        # frp type: direct
        else:
            rnd_port_list = DockerUtils.get_available_rnd_ports(port_range, 1)
            if len(rnd_port_list) == 0:
                raise DockerUtils.SafeProtectError("No available ports")
            rnd_port = rnd_port_list[0]
            for sv_name in conf["services"]:
                conf_sv = conf["services"][sv_name]
                if "ports" in conf_sv:
                    new_sv_p = []
                    conf_sv_p = conf_sv["ports"]
                    for i in range(len(conf_sv_p)):
                        port_arrays = conf_sv_p[i].split(":")
                        if len(port_arrays) == 1:
                            pass
                        elif len(port_arrays) == 2:
                            if port_arrays[0] == str(KEY_PORT):
                                new_sv_p.append(str(rnd_port) + ":" + port_arrays[1])
                        else:
                            raise DockerUtils.SafeProtectError(
                                "Invalid port format: {}".format(conf_sv_p[i])
                            )
                    conf_sv["ports"] = new_sv_p
            port_assigned = rnd_port

        """Dump and Return"""
        return yaml.dump(conf), port_assigned

    @staticmethod
    def up_docker_compose(user_id, challenge_id):
        try:
            configs = DBUtils.get_all_configs()
            basedir = os.environ["PROBLEM_FOLDER"]
            challenge = DynamicCheckChallenge.query.filter_by(
                id=challenge_id
            ).first_or_404()
            flag = (
                DockerUtils.gen_flag() if challenge.flag_type == "dynamic" else "static"
            )
            socket = DockerUtils.get_socket()
            frp_type = challenge.redirect_type.upper()
            frp_port = int(challenge.redirect_port)
            sname = os.path.join(basedir, challenge.dirname)
            # dirname = challenge.dirname.split("/")[1]
            # prefix = configs.get("docker_flag_prefix")
            category = challenge.category
            name = DockerUtils.get_name(user_id, challenge_id, category)
            docker_id = DockerUtils.get_docker_id(name)
            # TODO: UNKNOW ENVIRON
            problem_docker_run_dir = os.environ["PROBLEM_DOCKER_RUN_FOLDER"]
            dname = os.path.join(problem_docker_run_dir, name)
            min_port, max_port = int(configs.get("frp_direct_port_minimum")), int(
                configs.get("frp_direct_port_maximum")
            )

            # for local if not specified in docker-compose.yml
            image_name = (
                "ctfd-challenge"
                + challenge_id
                + "-"
                + resv_alnum(challenge.category)
                + "-"
                + resv_alnum(challenge.name)
            ).lower()
            image_tag = "latest"

        except subprocess.CalledProcessError as e:
            log(
                "owl",
                "Stdout: {out}\nStderr: {err}",
                out=e.stdout.decode(),
                err=e.stderr.decode(),
            )
            return e.stderr.decode()
        except Exception as e:
            print(traceback.format_exc())
            log("owl", e)
            return str(e)

        try:
            command = "mkdir -p '{dest}/' && cp -r -t '{dest}/' '{source}/'.".format(
                dest=dname, source=sname
            )
            process = subprocess.run(
                command,
                shell=True,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            compose_fp = os.path.join(dname, "docker-compose.yml")
            if not os.path.exists(compose_fp):
                compose_fp = os.path.join(dname, "docker-compose.yaml")
            if not os.path.exists(compose_fp):
                raise FileNotFoundError(
                    "docker-compose.yml or docker-compose.yaml not found"
                )

            compose_conf, port = DockerUtils.fmt_compose_file(
                content=open(compose_fp).read(),
                pwd=dname,
                local_image=(image_name, image_tag),
                port_range=(min_port, max_port),
                frp_type=frp_type,
                frp_http_container_name=None
                if frp_type != "HTTP"
                else DockerUtils.get_frp_http_container_name(name, docker_id),
            )
            open(os.path.join(dname, "run.yml"), "w").write(compose_conf)

            # force rebuild
            force_rebuild = os.path.exists(os.path.join(dname, ".rebuild"))
            opt_rebuild = " --build" if force_rebuild else ""

            # up docker-compose
            if flag != "static":
                open(os.path.join(dname, "flag"), "w").write(flag)
                command = "cd {} && echo FLAG={} >> .env && DOCKER_HOST={} docker compose -f run.yml up{} -d".format(
                    safe_quote(dname), safe_quote(flag), safe_quote(socket), opt_rebuild
                )
            else:
                command = (
                    "cd {} && DOCKER_HOST={} docker compose -f run.yml up{} -d".format(
                        safe_quote(dname), safe_quote(socket), opt_rebuild
                    )
                )
            process = subprocess.run(
                command,
                shell=True,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            # force rebuild: clean prune
            if force_rebuild:
                command = "cd {} && DOCKER_HOST={} docker image prune -f 2>&1 1>/dev/null".format(
                    safe_quote(dname), safe_quote(socket)
                )
                process = subprocess.run(
                    command,
                    shell=True,
                    check=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )

            if frp_type.upper() == "HTTP":
                # join network
                DockerUtils.join_network(
                    network_name=DockerUtils.get_frp_http_network_name(docker_id),
                    container_name=DockerUtils.get_frp_http_container_name(
                        name, docker_id
                    ),
                )

            log("owl", "[{date}] {msg}", msg=name + " up.")
            return (docker_id, port, flag, challenge.redirect_type)

        except subprocess.CalledProcessError as e:
            log(
                "owl",
                "Stdout: {out}\nStderr: {err}",
                out=e.stdout.decode(),
                err=e.stderr.decode(),
            )
            return e.stderr.decode()
        except DockerUtils.SafeProtectError as e:
            log("owl", e)
            return str(e)
        except Exception as e:
            print(traceback.format_exc())
            log("owl", e)
            return str(e)

    @staticmethod
    def down_docker_compose(user_id, challenge_id):
        try:
            configs = DBUtils.get_all_configs()
            basedir = os.environ["PROBLEM_FOLDER"]
            socket = DockerUtils.get_socket()
            challenge = DynamicCheckChallenge.query.filter_by(
                id=challenge_id
            ).first_or_404()
            # dirname = challenge.dirname.split("/")[1]
            # prefix = configs.get("docker_flag_prefix")
            category = challenge.category
            frp_type = challenge.redirect_type
            name = DockerUtils.get_name(user_id, challenge_id, category)
            problem_docker_run_dir = os.environ["PROBLEM_DOCKER_RUN_FOLDER"]
            dname = os.path.join(problem_docker_run_dir, name)
            c = DBUtils.get_container(user_id=user_id, challenge_id=challenge_id)

        except subprocess.CalledProcessError as e:
            log(
                "owl",
                "Stdout: {out}\nStderr: {err}",
                out=e.stdout.decode(),
                err=e.stderr.decode(),
            )
            return e.stderr.decode()
        except Exception as e:
            print(traceback.format_exc())
            log("owl", e)
            return str(e)

        try:

            command = "cd {} && DOCKER_HOST={} docker compose -f run.yml down".format(
                dname, safe_quote(socket)
            )
            process = subprocess.run(
                command,
                shell=True,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            command = "rm -rf {}".format(dname)
            process = subprocess.run(
                command,
                shell=True,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            if frp_type.upper() == "HTTP":
                # leave and remove network
                DockerUtils.remove_network(
                    network_name=DockerUtils.get_frp_http_network_name(c.docker_id)
                )

            log(
                "owl",
                "[{date}] {msg}",
                msg=name + " down.",
            )
            return True

        except subprocess.CalledProcessError as e:
            log(
                "owl",
                "Stdout: {out}\nStderr: {err}",
                out=e.stdout.decode(),
                err=e.stderr.decode(),
            )
            return e.stderr.decode()
        except DockerUtils.SafeProtectError as e:
            log("owl", e)
            return str(e)
        except Exception as e:
            print(traceback.format_exc())
            log("owl", e)
            return str(e)

    @staticmethod
    def remove_current_docker_container(user_id, challenge_id, is_retry=False):
        configs = DBUtils.get_all_configs()
        container = DBUtils.get_container(user_id=user_id, challenge_id=challenge_id)

        if container is None:
            return False
        try:
            DockerUtils.down_docker_compose(
                user_id, challenge_id=container.challenge_id
            )
            DBUtils.remove_current_container(user_id, container.challenge_id)
            return True
        except Exception as e:
            print(traceback.format_exc())
            # remove operation
            return False
