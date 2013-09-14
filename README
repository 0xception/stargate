.:OVERVIEW:.

StarGate is an asterisk integration application which allow you to build
modules/plugins which are able to register listeners on specific events or
commands. These modules/plugins are called chevrons which lock into stargate
(DON'T JUDGE MEH).

Protocols implemention consists of FastAGI and AMI. Each chevron can register
commands or event listeners with the stargate application on boot and callback
functions.

.:USAGE:.

To start the application we use the twistd framework which provides several
fun features. See /usr/local/stargate/env/bin/twistd --help

    % /usr/local/stargate/env/bin/twistd -l logs/stargate.log \
      --pidfile stargate.pid -y stargate.tac

NOTE: Make sure you are using the virtulenv before executing twistd or running
the application manually. To source the dir:

    % source /usr/local/stargate/env/bin/activate

.:LOGS:.

Logs are located in $BASE/logs/stargate.log
