import os
import subprocess

from CTFd.utils import set_config

from ..ctfd_whale.utils.setup import read_frpc_config
from .db_utils import DBUtils
from .extensions import log


def setup_default_configs():

    frpc_config = read_frpc_config()

    config = [
        ["owl_setup", "yes"],
        ["docker_api_url", "unix:///var/run/docker.sock"],
        ["docker_flag_prefix", "flag"],
        ["docker_max_container_count", "100"],
        ["docker_max_opened_count", "3"],
        ["docker_max_renew_count", "5"],
        ["docker_timeout", "3600"],
        ["docker_auto_connect_containers", "ctfd-frpc-1"],
        ["frp_api_url", "http://frpc:7400"],
        ["frp_direct_ip_address", "direct.test.com"],
        ["frp_http_domain_suffix", "dynamic.test.com"],
        ["frp_http_port", "80"],
        ["frp_direct_port_minimum", "31200"],
        ["frp_direct_port_maximum", "31399"],
        ["frpc_config_template", frpc_config],
    ]
    DBUtils.save_all_configs(config)

    try:
        basedir = os.path.dirname(__file__)
        destdir = os.environ["PROBLEM_FOLDER"]
        os.makedirs(destdir, exist_ok=True)
        command = "cp -r -t '{dest}/' '{base}/source/'.".format(
            base=basedir, dest=destdir
        )
        process = subprocess.run(
            command,
            shell=True,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

    except subprocess.CalledProcessError as e:
        log(
            "owl",
            "Stdout: {out}\nStderr: {err}",
            out=e.stdout.decode(),
            err=e.stderr.decode(),
        )
