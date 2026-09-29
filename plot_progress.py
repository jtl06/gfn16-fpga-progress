"""Render the public progress chart from explicitly qualified cycle measurements."""
from __future__ import annotations
import argparse
import json
import math
from pathlib import Path


def load_progress(path: Path) -> dict:
    data=json.loads(path.read_text())
    c=data["candidate"]
    if pow(c["base"],c["n"]).bit_length()!=c["exponent_bits"]:
        raise ValueError("exponent-bit count does not match candidate")
    if not math.isfinite(data["reference_clock_mhz"]) or data["reference_clock_mhz"]<=0:
        raise ValueError("invalid reference clock")
    seen=set()
    for row in data["milestones"]:
        if row["id"] in seen or row["cycles_per_square"]<=0:
            raise ValueError("duplicate milestone or invalid cycle count")
        if row["evidence_class"] not in {"component_model","integrated_rtl_simulation"}:
            raise ValueError("unknown evidence class")
        seen.add(row["id"])
    return data


def seconds(data, row):
    return row["cycles_per_square"]*data["candidate"]["exponent_bits"]/(data["reference_clock_mhz"]*1e6)


def duration(s):
    if s>=48*3600:return f"{s/86400:.1f} days"
    if s>=3600:return f"{s/3600:.1f} hours"
    return f"{s/60:.1f} min"


def render(data, destination):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D
    from matplotlib.ticker import FixedLocator, FixedFormatter, NullLocator
    plt.rcParams.update({"font.family":"DejaVu Sans", "font.size":11,
                         "svg.hashsalt":"gfn16-progress-v1", "svg.fonttype":"none"})
    rows=data["milestones"]; xs=list(range(len(rows)))
    ys=[seconds(data,row)/3600 for row in rows]
    blue="#2369a1"; gray="#687480"; green="#28734e"
    fig,ax=plt.subplots(figsize=(11.6,6.6),facecolor="white")
    fig.subplots_adjust(left=.12,right=.97,bottom=.32,top=.78)
    fig.text(.12,.935,"GFN-16: time-per-candidate progress",fontsize=21,color="#182d3c",weight="medium")
    fig.text(.12,.88,f"Architectural comparison at a hypothetical {data['reference_clock_mhz']:g} MHz • lower is better",color="#475966",fontsize=12)
    fig.text(.12,.835,"Compute-only projections from RTL cycle counts — not measured FPGA runtimes",color="#475966",fontsize=11)
    ax.set_yscale("log")
    lo,hi=[v/3600 for v in data["targets_seconds"]]
    ax.axhspan(lo,hi,color=green,alpha=.11,zorder=0)
    ax.text(.02,(lo*hi)**.5,"5–10 minute engineering goal · not achieved",transform=ax.get_yaxis_transform(),
            color=green,va="center",fontsize=10.5)
    ax.plot(xs,ys,color="#a8b6c0",linewidth=1.5,zorder=1)
    for x,y,row in zip(xs,ys,rows):
        component=row["evidence_class"]=="component_model"
        ax.scatter([x],[y],s=85 if component else 68,marker="D" if component else "o",
                   facecolor="white" if component else blue,edgecolor=gray if component else blue,
                   linewidth=1.7,zorder=3)
        ax.annotate(duration(y*3600),(x,y),xytext=(0,14),textcoords="offset points",
                    ha="center",color="#182d3c",fontsize=12,weight="medium")
    ticks=[5/60,10/60,1,6,24,168]
    ax.yaxis.set_major_locator(FixedLocator(ticks))
    ax.yaxis.set_major_formatter(FixedFormatter(["5 min","10 min","1 hour","6 hours","1 day","7 days"]))
    ax.yaxis.set_minor_locator(NullLocator())
    ax.set_ylim(min(lo*.5,min(ys)*.6),max(ys)*2.1)
    ax.set_xlim(-.3,len(rows)-.7)
    ax.set_xticks(xs,[r["label"] for r in rows],fontsize=10.5)
    ax.set_ylabel("Projected time per candidate (log scale)",labelpad=12,color="#334b5a")
    ax.set_xlabel("Development milestone — not elapsed time",labelpad=15,color="#475966")
    ax.grid(axis="y",color="#dae0e5",linewidth=.6)
    ax.set_axisbelow(True)
    for spine in ("top","right"):ax.spines[spine].set_visible(False)
    for spine in ("left","bottom"):ax.spines[spine].set_color("#bac5ce")
    ax.tick_params(axis="both",length=0,pad=9,labelcolor="#334b5a")
    legend=[Line2D([],[],linestyle="none",marker="D",markerfacecolor="white",markeredgecolor=gray,
                   markersize=7,label="Earlier component model"),
            Line2D([],[],linestyle="none",marker="o",color=blue,markersize=7,label="Integrated RTL simulation")]
    fig.legend(handles=legend,loc="lower left",bbox_to_anchor=(.115,.12),ncol=2,frameon=False,fontsize=10.5)
    fig.text(.12,.082,"Example: 604832956^65536 + 1 • 1,911,814 assumed square/conditional-double iterations",fontsize=10,color="#475966")
    fig.text(.12,.047,"Excludes proof/checkpoint/host work. Operating frequency remains design-dependent. Updated "+data["updated"]+".",fontsize=10,color="#475966")
    destination.mkdir(parents=True,exist_ok=True)
    for ext in ("svg","png"):
        metadata={"Date":None,"Creator":"GFN16 progress plotting script"} if ext=="svg" else {"Software":"GFN16 progress plotting script"}
        fig.savefig(destination/f"progress.{ext}",dpi=180,metadata=metadata)
    plt.close(fig)


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--data",type=Path,default=Path(__file__).with_name("progress.json"))
    ap.add_argument("--output",type=Path,default=Path(__file__).parent)
    args=ap.parse_args();data=load_progress(args.data);render(data,args.output)
    for row in data["milestones"]:print(row["id"],duration(seconds(data,row)))


if __name__=="__main__":main()
