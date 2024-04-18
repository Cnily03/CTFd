FROM php:7.4.30-apache

ENV FLAG=flag{this_is_a_test_flag}
COPY ./index.php /var/www/html/
COPY ./start.sh /var/start.sh
COPY ./flag /flag
RUN chmod +x /var/start.sh

EXPOSE 80

CMD ["/var/start.sh"]