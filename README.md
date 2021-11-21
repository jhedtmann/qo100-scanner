* off: power_on => initialising
* initialising: AUTO => idling
* idling: AUTO => idling | start => scanning



# Installation:
Copy all files including the "Scanner" folder to the /usr/script directory on the receiver.
In /etc/rc.local add the following line: /bin/sh /usr/script/start.sh & BEFORE the 'exit 0' line.

Alternatively create an entry in crontab.

# Remarks
* Because of frequent testing the live stream on http://db0kk.de and http://batc.org.uk/live/db0kk might experience interruptions. We apologise for any inconvenience.
* The scan list that the scanner uses has been reduced by every second channel as this speeds up scanning the transponder for the different symbol rates. Since the AFC of the RX is designed to cope with much wider signals, this generally poses no problem, except in cases where equally strong signals sit on adjacent channels.
