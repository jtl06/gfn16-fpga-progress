#!/usr/bin/env bash
# Run ONLY on aethia after the user has accepted the software EULA.
# Checks vendor payload hashes before executing the user-local installer.
set -euo pipefail
if [[ "${1:-}" != "--eula-approved" ]]; then
    echo 'Requires explicit EULA approval: --eula-approved' >&2
    exit 2
fi
if [[ "$(hostname -s)" != aethia ]]; then
    echo 'This installer is restricted to aethia.' >&2
    exit 2
fi
task_packages=/home/jtl/gfn-fpga-lab/tools/packages/quartus-pro-26.1
task_install=/home/jtl/gfn-fpga-lab/tools/altera_pro/26.1
if [[ -e "$task_install" ]]; then
    echo "Refusing to overwrite existing installation: $task_install" >&2
    exit 2
fi
cd "$task_packages"
sha1sum --check <<'CHECKSUMS'
694c03383a30c196440a22cb75f045cd1cdb40ef  QuartusProSetup-26.1.0.110-linux.run
99aab564ca8035beab7e083eaf2524b7cdbbb16e  QuartusProSetup-part2-26.1.0.110.qdz
f998b82882f664d9694f5ecee8292682499c23e5  arria10-26.1.0.110.qdz
CHECKSUMS
chmod u+x QuartusProSetup-26.1.0.110-linux.run
./QuartusProSetup-26.1.0.110-linux.run \
    --mode unattended --unattendedmodeui none --accept_eula 1 \
    --installdir "$task_install" --create_desktop_shortcuts 0 \
    --disable-components quartus_help,eda_simlib,eda_cdclib,agilex3,agilex5,agilex7,agilex_common,cyclone10gx,easicn5x,stratix10,quartus_update,riscfree,questa_fse,questa_fe,export_controlled,dsp_builder
"$task_install/quartus/bin/quartus_sh" --version
