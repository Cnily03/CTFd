import requests

from CTFd.plugins.ctfd_whale import Router

from .db_utils import DBUtils
from .docker_utils import DockerUtils
from .extensions import log
from .models import DynamicCheckChallenge


class FrpUtils:
    def get_rule(self):
        configs = DBUtils.get_all_configs()
        containers = DBUtils.get_all_alive_container()
        # frps config
        prefix = configs.get("docker_flag_prefix")

        http_template = (
            "\n\n[http_%s]\n"
            + "type = http\n"
            + "local_ip = %s\n"
            + "local_port = %s\n"
            + "subdomain = %s\n"
            + "use_compression = true"
        )

        direct_template = (
            "\n\n[direct_%s_tcp]\n"
            + "type = tcp\n"
            + "local_ip = %s\n"
            + "local_port = %s\n"
            + "remote_port = %s\n"
            + "use_compression = true"
            + "\n\n[direct_%s_udp]\n"
            + "type = udp\n"
            + "local_ip = %s\n"
            + "local_port = %s\n"
            + "remote_port = %s\n"
            + "use_compression = true"
        )
        output = ""
        for c in containers:
            dynamic_docker_challenge = DynamicCheckChallenge.query.filter(
                DynamicCheckChallenge.id == c.challenge_id
            ).first_or_404()
            # dirname = dynamic_docker_challenge.dirname.split("/")[1]
            redirect_port = dynamic_docker_challenge.redirect_port
            category = dynamic_docker_challenge.category
            name = DockerUtils.get_name(c.user_id, c.challenge_id, category)
            container_service_local_ip = DockerUtils.get_frp_http_container_name(
                name, c.docker_id
            )
            if dynamic_docker_challenge.redirect_type.upper() == "HTTP":
                output += http_template % (
                    container_service_local_ip,
                    container_service_local_ip,
                    redirect_port,
                    c.docker_id,
                )
            else:
                pass  # have been set in compose, no need to set again
                # output += direct_template % (
                #       container_service_local_ip
                #     , container_service_local_ip
                #     , redirect_port
                #     , c.port
                #     , container_service_local_ip
                #     , container_service_local_ip
                #     , redirect_port
                #     , c.port)
        return output

    def update_frp_redirect(self):
        configs = DBUtils.get_all_configs()
        output = ""
        if Router._name == "frp":
            rules = Router.get_rule()
            output = rules

        output += self.get_rule()
        if not output.startswith("\n"):
            output = "\n" + output
        output = configs.get("frpc_config_template") + output

        frp_api_url = configs.get("frp_api_url", "http://frpc:7400")
        if frp_api_url[-1] == "/":
            frp_api_url = frp_api_url[:-1]
        # print(output)
        try:
            if configs.get("frpc_config_template") is not None:
                assert (
                    requests.put(
                        frp_api_url + "/api/config", output, timeout=5
                    ).status_code
                    == 200
                )
                assert (
                    requests.get(frp_api_url + "/api/reload", timeout=5).status_code
                    == 200
                )
            else:
                pass
        except Exception as e:
            import traceback

            log("owl", "[ERROR]frp reload: {err}", err=traceback.format_exc())
            pass
