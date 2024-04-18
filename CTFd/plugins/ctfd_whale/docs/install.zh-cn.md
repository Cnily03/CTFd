# 使用指南

## TLDR

如果你从未部署过 CTFd，你可以通过执行:

```sh
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh --mirror Aliyun
docker swarm init
docker node update --label-add='name=linux-1' $(docker node ls -q)

git clone https://github.com/CTFd/CTFd --depth=1
git clone https://github.com/frankli0324/ctfd-whale CTFd/CTFd/plugins/ctfd_whale --depth=1
curl -fsSL https://cdn.jsdelivr.net/gh/frankli0324/ctfd-whale/docker-compose.example.yml -o CTFd/docker-compose.yml

# make sure you have pip3 installed on your rig
pip3 install docker-compose
docker-compose -f CTFd/docker-compose.yml up -d
docker-compose -f CTFd/docker-compose.yml exec ctfd python manage.py
```

脚本会在一台 Linux 机器上安装 **_docker.com 版本的_** `docker-ce`，`python3-pip` 以及 `docker-compose`，请确保执行上述代码之前：

- 安装好 curl，git，python3 以及 pip
- 网络环境良好，能正常从 GitHub 克隆仓库
- 网络环境良好，能正常从 Docker Registry 拖取镜像

## 手动安装

为了更好地理解 ctfd-whale 各个组件的作用，更充分地利用 ctfd-whale，在真实使用 ctfd-whale 时建议用户手动、完整地从空白 CTFd 开始搭建一个实例。下面本文将引导你完成整个流程。

### 从零开始

首先需要初始化一个 swarm 集群并给节点标注名称

linux 节点名称需要以 `linux-` 打头，windows 节点则以 `windows-` 打头

```bash
docker swarm init
docker node update --label-add "name=linux-1" $(docker node ls -q)
```

`ctfd-whale`利用`docker swarm`的集群管理能力，能够将题目容器分发到不同的节点上运行。选手每次请求启动题目容器时，`ctfd-whale`都将随机选择一个合适的节点运行这个题目容器。

然后，我们需要确保 CTFd 可以正常运行。

注意，2.5.0+版本 CTFd 的 `docker-compose.yml` 中包含了一个 `nginx` 反代，占用了 80 端口

```bash
git clone https://github.com/CTFd/CTFd --depth=1
cd CTFd  # 注：以下全部内容的cwd均为此目录
```

先将 `docker-compose.yml` 的第一行进行修改，以支持 `attachable` 参数

`version '2'` -> `version '3'`

接着

```bash
docker-compose up -d
```

访问<http://localhost>（或 8000 端口），对 CTFd 进行初始配置

### 配置 frps

frps 可以直接通过 docker-compose 与 CTFd 同步启动。

首先在 networks 中添加一个网络，用于 frpc 与 frps 之间的通信，并添加 frps service

```yml
services:
    ...
    frps:
        image: glzjin/frp
        restart: always
        volumes:
            - ./conf/frp:/conf
        entrypoint:
            - /usr/local/bin/frps
            - -c
            - /conf/frps.ini
        ports:
            - 10000-10100:10000-10100  # 映射direct类型题目的端口
            - 8001:8001  # 映射http类型题目的端口
        networks:
            default:  # 需要将frps暴露到公网以正常访问题目容器
            frp_connect:

networks:
    ...
    frp_connect:
        driver: overlay
        internal: true
        ipam:
            config:
                - subnet: 172.1.0.0/16
```

先创建目录 `./conf/frp`

```bash
mkdir ./conf/frp
```

接着创建 `./conf/frp/frps.ini` 文件，填写：

```ini
[common]
# 下面两个端口注意不要与direct类型题目端口范围重合
bind_port = 7987  # frpc 连接到 frps 的端口
vhost_http_port = 8001  # frps 映射http类型题目的端口
token = your_token
subdomain_host = node3.buuoj.cn  # 访问http题目容器的主机名
```

### 配置 frpc

同样，在 networks 中再添加一个网络，用于 frpc 与题目容器之间的通信，并添加 frpc service

```yml
services:
    ...
    frpc:
        image: glzjin/frp:latest
        restart: always
        volumes:
          - ./conf/frp:/conf/
        entrypoint:
          - /usr/local/bin/frpc
          - -c
          - /conf/frpc.ini
        depends_on:
          - frps #frps需要先成功运行
        networks:
            frp_containers:  # 供frpc访问题目容器
            frp_connect:  # 供frpc访问frps, CTFd访问frpc
                ipv4_address: 172.1.0.3

networks:
    ...
    frp_containers:
        driver: overlay
        internal: true  # 如果允许题目容器访问外网，则可以去掉
        attachable: true
        ipam:
            config:
                - subnet: 172.2.0.0/16
```

同样，我们需要创建一个 `./conf/frp/frpc.ini`

```ini
[common]
token = your_token
server_addr = frps
server_port = 7897  # 对应 frps 的 bind_port
admin_addr = 172.1.0.3  # 请参考“安全事项”
admin_port = 7400
```

### 检查 frp 配置是否正确

此时可以执行 `docker-compose up -d` 更新 compose 配置

通过查看日志 `docker-compose logs frpc` ，应当能看到 frpc 产生了以下日志：

```log
[service.go:224] login to server success, get run id [******], server udp port [******]
[service.go:109] admin server listen on ******
```

说明 frpc 与 frps 皆配置正常

注：此例中目录结构为：

```
CTFd/
    conf/
        nginx  # CTFd 2.5.0+中自带
        frp/
            frpc.ini
            frps.ini
    serve.py
```

### 配置 CTFd

前面的工作完成后，将本机 docker 的访问接口映射到 CTFd 所在容器内

并将 CTFd 添加到 frpc 所在 network 中（注意不是 containers 这个 network）

```yml
services:
    ctfd:
        ...
        volumes:
            - /var/run/docker.sock:/var/run/docker.sock
        depends_on:
            - frpc #frpc需要先运行
        networks:
            ...
            frp_connect:
```

将 CTFd-Whale 克隆至 CTFd 的插件目录

```bash
git clone https://github.com/frankli0324/CTFd-Whale CTFd/plugins/ctfd_whale --depth=1
docker-compose build # 需要安装依赖
docker-compose up -d
```

进入 Whale 的配置页面( `/plugins/ctfd-whale/admin/settings` )，首先配置 docker 配置项

需要注意的是 `Auto Connect Network` ，如果按照上面的配置流程进行配置的话，应当是 `ctfd_frp_containers`

如果不确定的话，可以通过下面的命令列出 CTFd 目录 compose 生成的所有 network

```bash
docker network ls -f "label=com.docker.compose.project=ctfd" --format "{{.Name}}"
```

然后检查 frp 配置项是否正确

- `HTTP Domain Suffix` 与 frps 的 `subdomain_host` 保持一致
- `HTTP Port` 与 frps 的 `vhost_http_port` 保持一致
- `Direct IP Address` 为能访问到 frps 相应端口(例子中为 10000-10100) 的 IP
- `Direct Minimum Port` 与 `Direct Maximum Port` 显然可得
- 只要正确填写了 `API URL` ，Whale 会自动获取 frpc 的配置文件作为 `Frpc config template`
- 通过设置 `Frpc config template` 可以覆盖原有 `frpc.ini` 文件

至此，CTFd-Whale 已经马马虎虎可以正常使用了。

### 配置 nginx

如果你在使用 2.5.0+版本的 CTFd，那么你可以直接利用自带的 nginx 进行 http 题目的反代

首先去除 docker-compose.yml 中对 frps http 端口的映射(8001)
如果想贯彻到底的话，可以

- 为 nginx 添加 internal 与 default 两个 network
- 去除 CTFd 的 default network，并去除 ports 项

在 `./conf/nginx/nginx.conf` 的 http block 中添加以下 server block

```conf
server {
  listen 80;
  server_name *.node3.buuoj.cn;
  location / {
    proxy_pass http://frps:8001;
    proxy_redirect off;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Host $server_name;
  }
}
```

## 部署题目

### 单容器题目环境

请参考<https://github.com/CTFTraining>中的镜像进行题目镜像制作（Dockerfile 编写）。总体而言，题目在启动时会向**容器**内传入名为 `FLAG` 的环境变量，你需要编写一个启动脚本（一般为 bash+sed 组合拳）将 flag 写入自己的题目中，并删除这一环境变量。

请出题人制作镜像时请理清思路，不要搞混容器与镜像的概念。这样既方便自己，也方便部署人员。

### 多容器题目环境

在题目镜像名处填写一个 json object，即可创建一道多容器的题目

```json
{
  "hostname": "image"
}
```

Whale 会保留 json 的 key 顺序，并将第一个容器作为"主容器"映射到外网，映射方式与单容器相同
以 buuoj 上的 swpu2019 web2 为例，可以配置如下：

```json
{
    "ss": "shadowsocks-chall",
    "web": "swpu2019-web2",
    ...
}
```

其中 shadowsocks-chall 的 Dockerfile:

```dockerfile
FROM shadowsocks/shadowsocks-libev
ENV PASSWORD=123456
ENV METHOD=aes-256-cfb
```

> 注：由于写 README 的并不是 buuoj 管理员，故上述仅作说明用，与实际情况可能有较大出入

## 安全事项

- 后台配置中 flag 与 domain 模版理论上存在 ssti（feature），请不要将管理员账号给不可信第三方
- 由于例子中 frpc 并没有开启鉴权，请不要将 frpc 的 bind_addr 设置为`0.0.0.0`。这样会导致利用任何一道能发起 http 请求的题目都能修改 frpc 配置。
- 如果出于配置复杂性考虑，题目容器能够访问 frpc，请开启 frpc 的 Basic Auth，并以 `http://username:password@frpc:7400` 的格式设置 frpc API URL

## 高级部署

用于下发靶机实例的服务器与运行 `CTFd` 网站的服务器分离，`CTFd-whale` 通过启用了 `TLS/SSL` 验证的 `Dockers API`进行下发容器控制

参见 [advanced.zh-cn.md](advanced.zh-cn.md)
