// SPDX-License-Identifier: Apache-2.0
// Real BOINC SDK adapter; compile only against pinned BOINC 8.2.9 headers/libs.
// No client, server, device, upload or project-specific format integration.
#include "boinc_api.h"
#include <unistd.h>

extern "C" int r15_sdk_init() {
    // Refuse real client launch data BEFORE initialization/shared-memory setup.
    if (access("init_data.xml", F_OK) == 0) return -9001;
    BOINC_OPTIONS options;
    boinc_options_defaults(options);
    options.direct_process_action = 0;
    options.multi_thread = 1; // Python runtime plus the SDK timer thread.
    int rc = boinc_init_options(&options);
    if (rc) return rc;
    return boinc_is_standalone() ? 0 : -9002;
}
extern "C" int r15_sdk_standalone() { return boinc_is_standalone(); }
extern "C" int r15_sdk_status() {
    BOINC_STATUS s{};
    int rc = boinc_get_status(&s);
    if (rc) return -1;
    return (s.suspended ? 1 : 0) | (s.quit_request ? 2 : 0)
        | (s.abort_request ? 4 : 0) | (s.no_heartbeat ? 8 : 0);
}
extern "C" int r15_sdk_resolve(const char* name, char* path, int size) {
    return boinc_resolve_filename(name, path, size);
}
extern "C" int r15_sdk_checkpoint_due() {
    const int due = boinc_time_to_checkpoint();
    // This small standalone test checkpoints every verified window. If the
    // SDK timer did not request one, explicitly bracket our extra checkpoint.
    if (!due) boinc_begin_critical_section();
    return due;
}
extern "C" int r15_sdk_checkpoint_done() { return boinc_checkpoint_completed(); }
extern "C" int r15_sdk_progress(double value) { return boinc_fraction_done(value); }
extern "C" double r15_sdk_fraction() { return boinc_get_fraction_done(); }
extern "C" int r15_sdk_finish(int status) { return boinc_finish(status); }
