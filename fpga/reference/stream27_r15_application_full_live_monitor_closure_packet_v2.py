"""Use the unchanged existing packet API against additive observer closure."""
import json
from fpga.reference import stream27_r15_application_full_live_monitor_packet_v9 as packet
from fpga.reference import stream27_r15_application_full_live_monitor_closure_v2 as closure


def prepare():
    packet.own=closure
    return packet.prepare()


if __name__=='__main__':print(json.dumps(prepare(),indent=2))
