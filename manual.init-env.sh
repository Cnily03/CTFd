#!/bin/bash
UUID=$(cat /proc/sys/kernel/random/uuid)

# set value here
# CTFD_URL=
# DIRECT_URL=
# DYNAMIC_URL=
# UUID=

# original value
ORI_CTFD_URL=ctfd.test.com
ORI_DIRECT_URL=direct.test.com
ORI_DYNAMIC_URL=dynamic.test.com
ORI_UUID=YOUR_TOKEN

sed -i "s/$ORI_DYNAMIC_URL/$DYNAMIC_URL/g" /opt/CTFd/CTFd/plugins/ctfd_whale/utils/setup.py
sed -i "s/$ORI_DIRECT_URL/$DIRECT_URL/g" /opt/CTFd/CTFd/plugins/ctfd_whale/utils/setup.py
sed -i "s/$ORI_UUID/$UUID/g" /opt/CTFd/CTFd/plugins/ctfd_whale/utils/setup.py

sed -i "s/$ORI_DYNAMIC_URL/$DYNAMIC_URL/g" /opt/CTFd/CTFd/plugins/ctfd_owl/setup.py
sed -i "s/d$ORI_DIRECT_URL/$DIRECT_URL/g" /opt/CTFd/CTFd/plugins/ctfd_owl/setup.py
sed -i "s/$ORI_UUID/$UUID/g" /opt/CTFd/CTFd/plugins/ctfd_owl/setup.py

sed -i "s/$ORI_CTFD_URL/$CTFD_URL/g" /opt/CTFd/conf/nginx/http.conf
sed -i "s/$ORI_DYNAMIC_URL/$DYNAMIC_URL/g" /opt/CTFd/conf/nginx/http.conf
sed -i "s/$ORI_DIRECT_URL/$DIRECT_URL/g" /opt/CTFd/conf/nginx/http.conf

sed -i "s/$ORI_DYNAMIC_URL/$DYNAMIC_URL/g" /opt/CTFd/conf/frp/frps.ini
sed -i "s/$ORI_UUID/$UUID/g" /opt/CTFd/conf/frp/frps.ini

sed -i "s/$ORI_UUID/$UUID/g" /opt/CTFd/conf/frp/frpc.ini
