* off: power_on => initialising
* initialising: AUTO => idling
* idling: AUTO => idling | start => scanning



# Installation:
Copy all files including the "Scanner" folder to the /usr/script directory on the receiver.
In /etc/rc.local add the following line: /bin/sh /usr/script/start.sh & BEFORE the 'exit 0' line.

Alternatively create an entry in crontab.