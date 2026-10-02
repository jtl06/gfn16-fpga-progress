# Plain compute-only syn/fit/multi-corner STA; no assembler.
load_package project
load_package flow
cd [file dirname [file normalize [info script]]]
project_open probe
if {[catch {
    execute_module -tool syn
    execute_module -tool fit
    execute_module -tool sta
} failure]} {
    catch {project_close}
    error $failure
}
catch {project_close}
