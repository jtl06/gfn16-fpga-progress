"""Exhaustive small bank-index proof for the folded NTT root permutation."""


def rol(value: int, rotation: int, width: int) -> int:
    return ((value << rotation) | (value >> (width-rotation))) & ((1 << width)-1)


def prove() -> dict:
    checks=0
    for width in range(1,8):
        banks=1 << width
        # Includes every supported early-stage broadcast and the unmasked case.
        for mask_bits in range(width+1):
            mask=(1 << mask_bits)-1
            for rotation in range(width):
                for data_base in range(banks):
                    folded=rol(data_base & mask,rotation,width)
                    for bank in range(banks):
                        old=rol((bank ^ data_base) & mask,rotation,width)
                        new=rol(bank & mask,rotation,width) ^ folded
                        if old != new:
                            raise AssertionError((width,mask_bits,rotation,data_base,bank))
                        checks+=1
    # Both expressions then XOR the same arbitrary root_base, so equality above
    # proves equality for every root_base without enumerating a redundant axis.
    return {"passed":True,"checks":checks,"bank_index_widths":list(range(1,8)),
            "root_base":"arbitrary common XOR; cancels in equality",
            "scope":"index identity, not RTL timing or pipeline alignment"}


if __name__ == "__main__":
    import json
    print(json.dumps(prove(),indent=2))
