import sys

from CTFd.utils import set_config

from ..models import WhaleRedirectTemplate, db


def read_frpc_config():
    frpc_path = "/opt/CTFd/conf/frp/frpc.ini"
    frpc_config = "[common]\r\ntoken = YOUR_TOKEN\r\nserver_addr = frps\r\nserver_port = 9123\r\nadmin_addr = 0.0.0.0\r\ndmin_port = 7400\r\npool_count = 200\r\ntls_enable = true\r\n\r\n"
    try:
        with open(frpc_path, "r") as f:
            frpc_config = f.read()
    except FileNotFoundError:
        sys.stderr.write("Error: {} not found\n".format(frpc_path))
    finally:
        frpc_config = frpc_config.replace("\r\n", "\n")
        frpc_config = frpc_config.strip() + "\n\n"
    return frpc_config


def setup_default_configs():

    frpc_config = read_frpc_config()

    for key, val in {
        "setup": "true",
        "docker_api_url": "unix:///var/run/docker.sock",
        "docker_credentials": "",
        "docker_dns": "127.0.0.1",
        "docker_max_container_count": "100",
        "docker_max_opened_count": "3",
        "docker_max_renew_count": "5",
        "docker_subnet": "174.1.0.0/16",
        "docker_subnet_new_prefix": "24",
        "docker_swarm_nodes": "linux-1",
        "docker_timeout": "3600",
        "docker_auto_connect_network": "ctfd_frp_containers",
        "docker_auto_connect_containers": "ctfd-frpc-1",
        "frp_api_url": "http://frpc:7400",
        "frp_http_port": "80",
        "frp_http_domain_suffix": "dynamic.test.com",
        "frp_direct_ip_address": "direct.test.com",
        "frp_direct_port_minimum": "31000",
        "frp_direct_port_maximum": "31199",
        "template_http_subdomain": "{{ container.uuid }}",
        "template_chall_flag": '{{ "flag{"+uuid.uuid4()|string+"}" }}',
        "frp_config_template": frpc_config,
    }.items():
        set_config("whale:" + key, val)
    db.session.add(
        WhaleRedirectTemplate(
            "http",
            "http://{{ container.http_subdomain }}."
            '{{ get_config("whale:frp_http_domain_suffix", "") }}'
            '{% if get_config("whale:frp_http_port", "80") != 80 %}:{{ get_config("whale:frp_http_port") }}{% endif %}/',
            """
[http_{{ container.user_id|string }}-{{ container.uuid }}]
type = http
local_ip = {{ container.user_id|string }}-{{ container.uuid }}
local_port = {{ container.challenge.redirect_port }}
subdomain = {{ container.http_subdomain }}
use_compression = true
""",
        )
    )
    db.session.add(
        WhaleRedirectTemplate(
            "direct",
            'nc {{ get_config("whale:frp_direct_ip_address", "127.0.0.1") }} {{ container.port }}',
            """
[direct_{{ container.user_id|string }}-{{ container.uuid }}]
type = tcp
local_ip = {{ container.user_id|string }}-{{ container.uuid }}
local_port = {{ container.challenge.redirect_port }}
remote_port = {{ container.port }}
use_compression = true

[direct_{{ container.user_id|string }}-{{ container.uuid }}_udp]
type = udp
local_ip = {{ container.user_id|string }}-{{ container.uuid }}
local_port = {{ container.challenge.redirect_port }}
remote_port = {{ container.port }}
use_compression = true
""",
        )
    )
    db.session.commit()
