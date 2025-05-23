# ais_project

ais_main.py - the entire program for the device including UI/transmission functionality (not up to date with new changes to encoding/decoding/tranmission, waiting to achieve success beofore changing this.)

[receiver] ais_verify.py - script that runs rtl-ais tool with rtlSDR in order to verify/receive incoming AIS traffic and break down into raw binary along with transmission sentence for testing. 

[transmit] hackrf_cli_transmit.py - simple streamlined script to transmit AIS sentence using hackrf cli tools directly... encoding/decoding process is believed to be correct in this implementation.

[dr-elias] standard_compliant_ais_main.py - edited script of ais_main.py with difference in AIS standard encoding process

test_raw_cli_fixed.py - script to test transmission of raw binary from real message through hackrf cli tools to simplify process 

ais_relay.py - relay script that captures AIS signals into .iq files and replays them using HackRF to the same frequency.  for hackrf setup testing and AIS transmission testing.


most important right now for testing successful transmission:

1) using rtlSDR running ais_verify.py to receive traffic (python3 ais_verify.py)
2) then run "python3 hackrf_cli_transmit.py" to send a loop of AIS signals for transmission testing

if successful traffic should look like:
new_venvpeytonandras@P nato_navy % python3 ais_verify.py
⧉ rtl_ais -g 38 -p 0 -n
▶ listening …
─────────────────────────────────────────────────
01:15:31  !AIVDM,1,1,,A,15NNevP000qNMgpAHv4EVAa00<1s,0*32
1:[0, 0, 0, 0, 0, 1] 5:[0, 0, 0, 1, 0, 1] N:[0, 1, 1, 1, 1, 0] N:[0, 1, 1, 1, 1, 0] e:[1, 0, 1, 1, 0, 1] v:[1, 1, 1, 1, 1, 0] P:[1, 0, 0, 0, 0, 0] 0:[0, 0, 0, 0, 0, 0] 0:[0, 0, 0, 0, 0, 0] 0:[0, 0, 0, 0, 0, 0] q:[1, 1, 1, 0, 0, 1] N:[0, 1, 1, 1, 1, 0] M:[0, 1, 1, 1, 0, 1] g:[1, 0, 1, 1, 1, 1] p:[1, 1, 1, 0, 0, 0] A:[0, 1, 0, 0, 0, 1] H:[0, 1, 1, 0, 0, 0] v:[1, 1, 1, 1, 1, 0] 4:[0, 0, 0, 1, 0, 0] E:[0, 1, 0, 1, 0, 1] V:[1, 0, 0, 1, 1, 0] A:[0, 1, 0, 0, 0, 1] a:[1, 0, 1, 0, 0, 1] 0:[0, 0, 0, 0, 0, 0] 0:[0, 0, 0, 0, 0, 0] <:[0, 0, 1, 1, 0, 0] 1:[0, 0, 0, 0, 0, 1] s:[1, 1, 1, 0, 1, 1]
────────────────────────────────────────────────

3) GQRX is the signal analyzer that can also be used with the rtlSDR to verify signal strength and transmission (cannot use ais_verify.py and GQRX at the same time)

4) Channel A - 161.975MHz, Channel B - 162MHz