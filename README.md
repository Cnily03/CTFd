# CTFd

个人定制化的 CTFd 部署方案

## 集成

插件

- Whale
- Owl

实现的功能

- [x] 支持容器多开
- [x] 支持前 N 血动态积分（含设置）
- [x] 支持 Webhook
- [x] Owl 环境挂载 flag
- [x] Owl 文件挂载 flag
- [x] Owl 子域名访问题目
- [x] Owl 端口访问题目
- [x] Owl docker compose 安全检查（防止穿越泄漏宿主机文件）
- [x] Owl 支持本地镜像覆盖构建

## 快速安装

根据注释内容运行 `manual.docker-swarm.sh` 完成 docker 集群部署

修改 `manual.init-env.sh`，取消下面几行的注释，进行值的替换，然后运行它

```ini
CTFD_URL=    # 网站域名
DIRECT_URL=  # 使用端口访问容器的域名
DYNAMIC_URL= # 使用动态子域名访问容器的域名
FRP_TOKEN=   # Frp 的 Token
```

> [!Caution]
> 脚本 `manual.init-env.sh` 运行后后将无法自动恢复运行前的状况，请慎重操作

此外，我们建议参照注释修改 `docker-compose.yml` 文件，例如你可能需要修改数据库密码、端口映射等

## 使用方法

题目样例位于 `CTFd/plugins/ctfd_owl/source` 目录下，一个 `docker-compose.yml` 的样例如下

### 挂载方式

容器运行时会在 `docker-compose.yml` 同级目录下生成 `flag` 和 `.env` 文件，可以通过文件挂载或环境变量的方式引入 flag

```yaml
services:
  web:
    build: .
    volumes:
      - "$PWD/flag:/flag:ro" # 如果需要文件挂载，可以使用这种方式
    environment:
      TZ: Asia/Shanghai
      FLAG: ${FLAG} # 如果需要环境变量挂载，可以使用这种方式
    restart: always
    ports:
      - 9999:80
    networks:
      default:
      # public:

networks:
  default:
  # public:
  #   external:
  #      name: frp_containers
```

### Frp 方式（DIRECT）

在端口中使用 `9999:<port>` 的方式，其中 `9999` 会被替换为随机端口

```yaml
services:
  web:
    ports:
      - 9999:80
```

### Frp 方式（HTTP）

当只有一个 service 时，你不需要做任何事，Frp HTTP 模式会自动在该容器映射 HTTP 端口

如果有多个 service，你需要在 `docker-compose.yml` 中指定 `container_name` 为 `frp-http`，以告知在该容器（而不是其它 service 对应的容器）映射 HTTP 端口

```yaml
services:
    web:
        # 当出现多个 service 时，可以指定 container_name 为 `frp-http`，以告知在该容器映射 HTTP 端口
        container_name: frp-http
        ...
    ext:
        ...
```

如果你希望重新构建镜像，你只需要在与 `docker-compose.yml` 同级目录下新建文件 `.rebuild` 即可

当 CTFd 容器启动后，题目目录默认位于宿主机的 `.data/CTDd/problem` 目录，题目运行时目录默认位于 `/tmp/ctfd-problem-docker-run` 目录，可以通过修改 `docker-compose.yml` 来进行更改

## 许可证

Apache-2.0
