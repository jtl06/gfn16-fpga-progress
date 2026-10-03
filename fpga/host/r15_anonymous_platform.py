# SPDX-License-Identifier: Apache-2.0
"""Pure, default-OFF rendering of one explicitly supplied BOINC app version.

This is an offline XML subset, NOT a PrimeGrid profile, workunit/result parser,
BOINC client integration, binary installer, or deployment permission. No project
names, versions, file roles, accelerator type, or resource defaults are guessed.
Fields follow BOINC d56d870 client/{cs_statefile,client_types}.cpp and
https://github.com/BOINC/boinc/wiki/Anonymous-platform . No upstream code copied.
"""

import math
import re
import xml.etree.ElementTree as ET


class ManifestError(ValueError):
    pass


def _need(ok, reason):
    if not ok:
        raise ManifestError(reason)


def _name(value):
    # A conservative portable filename/identifier subset, not all BOINC names.
    _need(type(value) is str and len(value) <= 127 and
          re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*', value) is not None and
          '..' not in value, 'OFFLINE_APP_NAME')
    return value


def _text(value, limit=255):
    _need(type(value) is str and all(
        0x20 <= ord(c) <= 0xD7FF or 0xE000 <= ord(c) <= 0xFFFD or
        0x10000 <= ord(c) <= 0x10FFFF for c in value), 'OFFLINE_APP_TEXT')
    _need(len(value.encode('utf-8')) <= limit, 'OFFLINE_APP_TEXT_BYTES')
    return value


def render_app_info(*, app_name, version_num, api_version, platform, executable,
                    cmdline, plan_class, avg_ncpus, support_files, enabled=False):
    """Return XML bytes only; caller must supply every deployment-dependent field.

    support_files is a list of (physical application filename, logical open_name)
    tuples. These are application resources, NOT server task inputs/outputs.
    The bounded subset supports no coprocessor declaration or automatic platform
    selection. XML escaping does not validate project acceptance or a command.
    """
    _need(enabled is True, 'OFFLINE_APP_RENDER_OFF')
    _name(app_name)
    _name(platform)
    _name(executable)
    _need(type(version_num) is int and 0 <= version_num <= 2147483647,
          'OFFLINE_APP_VERSION')
    _need(type(api_version) is str and len(api_version) <= 15 and
          re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+', api_version) is not None,
          'OFFLINE_APP_API_VERSION')
    _text(cmdline)
    _text(plan_class, limit=63)
    _need(type(avg_ncpus) in (int, float) and
          0 < avg_ncpus <= 64 and math.isfinite(avg_ncpus),
          'OFFLINE_APP_CPU_COUNT')
    _need(type(support_files) is list and len(support_files) <= 32,
          'OFFLINE_APP_FILES')
    filenames, logical_names = {executable}, {executable}
    for pair in support_files:
        _need(type(pair) is tuple and len(pair) == 2, 'OFFLINE_APP_FILE_REF')
        filename, logical = map(_name, pair)
        _need(filename not in filenames and logical not in logical_names,
              'OFFLINE_APP_DUPLICATE_FILE')
        filenames.add(filename)
        logical_names.add(logical)

    root = ET.Element('app_info')
    ET.SubElement(ET.SubElement(root, 'app'), 'name').text = app_name
    for filename in [executable] + [pair[0] for pair in support_files]:
        file = ET.SubElement(root, 'file_info')
        ET.SubElement(file, 'name').text = filename
        if filename == executable:
            ET.SubElement(file, 'executable')
    version = ET.SubElement(root, 'app_version')
    for tag, value in (('app_name', app_name), ('version_num', str(version_num)),
                       ('api_version', api_version), ('platform', platform),
                       ('plan_class', plan_class), ('avg_ncpus', str(avg_ncpus)),
                       ('cmdline', cmdline)):
        ET.SubElement(version, tag).text = value
    main = ET.SubElement(version, 'file_ref')
    ET.SubElement(main, 'file_name').text = executable
    ET.SubElement(main, 'main_program')
    for filename, logical in support_files:
        ref = ET.SubElement(version, 'file_ref')
        ET.SubElement(ref, 'file_name').text = filename
        ET.SubElement(ref, 'open_name').text = logical
    ET.indent(root, space='  ')
    return ET.tostring(root, encoding='utf-8', xml_declaration=True) + b'\n'
