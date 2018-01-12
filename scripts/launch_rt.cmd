:: Usage:  scripts\launch_rt.cmd
::
:: Connect Rising Thunder to a local instance of the server running on port 1337.
:: Assumes you have a copy of RT in ..\Rising Thunder

set tb.gameinst=ServerUri=http://localhost:1337/_01/
start "..\RisingThunder\RisingThunder.exe"

