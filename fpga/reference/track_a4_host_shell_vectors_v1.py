"""Early executable shell commands; no mock square success or NTT claim."""
import hashlib
from fpga.reference.track_a4_control_model_v1 import Controller


def corpus(aw=5):
    if aw not in (5, 8):
        raise ValueError("early shell AW5/AW8 only")
    n = 1 << aw
    model = Controller(n)
    minimum = max(2*n+5, (2*(2*n+384)+2)//3+1)
    opcodes = {"RELOAD_BEGIN":0,"LOAD_WORD":1,"READ":2,"WRITE":3,"SET_BASE":4,"BAD":7}
    errors = {None:0,"unsupported_base":1,"reload_order_or_digit":2,"image_not_ready":3,
              "host_digit":4,"opcode":5,"new_base_digit_reject_reload_required":9}
    rows = []
    def command(op, address=0, word=0, base=0):
        assert model.request(op,address=address,word=word,base=base)
        response=model.finish()
        rows.append((opcodes[op],address,word & 0xffffffff,base,errors[response.error],
                     (response.word or 0)&0xffffffff,int(model.image is not None and model.state=="ready"),int(model.fault_sticky)))
    def reload(base,values):
        command("RELOAD_BEGIN",base=base)
        for address,word in enumerate(values):command("LOAD_WORD",address,word)
    command("RELOAD_BEGIN",base=minimum-1)
    reload(1000,[(i*73+17)%1000 for i in range(n)])
    for address in (0,n//2,n-1):command("READ",address)
    command("WRITE",0,-1)
    command("READ",0)
    command("SET_BASE",base=2000)
    for address in (0,1,n-1):command("READ",address)
    command("SET_BASE",base=minimum)
    reload(minimum,[-1]+[0]*(n-1))
    command("READ",0);command("READ",n-1)
    command("WRITE",0,7);command("READ",0)
    command("WRITE",n-1,-1);command("READ",0);command("READ",n-1)
    command("SET_BASE",base=minimum-1)
    command("RELOAD_BEGIN",base=minimum)
    command("LOAD_WORD",1,0)
    reload(minimum,[0]*n)
    command("BAD")
    reload(minimum,[3]*n)
    command("READ",0)
    text=f"A4HOST1 {aw} {len(rows)}\n"+"\n".join(" ".join(map(str,row)) for row in rows)+"\n"
    return text,dict(aw=aw,commands=len(rows),readbacks=sum(r[0]==2 for r in rows),errors=sum(r[4]!=0 for r in rows),
        sha256=hashlib.sha256(text.encode()).hexdigest(),scope="Real host/setup/canonical shell only; square backend disabled")
