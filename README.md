* off: power_on => initialising
* initialising: AUTO => idling
* idling: AUTO => idling | start => scanning



# Installation:
Copy all files including the "Scanner" folder to the /usr/script directory on the receiver.
In /etc/rc.local add the following line: /bin/sh /usr/script/start.sh & BEFORE the 'exit 0' line.

Alternatively create an entry in crontab.

# Remarks
* Because of frequent testing the live stream on http://db0kk.de and http://batc.org.uk/live/db0kk might experience interruptions. We apologise for any inconvenience.
