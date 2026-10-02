## Generated SDC file "/home/azureuser/gfn16-worker/audit-output-s4-p16-diet-whole-9000-azure-clockprobe-v1-audit4/timing/selected-3-effective.sdc"

## Copyright (C) 2026  Altera Corporation. All rights reserved.
## Your use of Altera Corporation's design tools, logic functions 
## and other software and tools, and any partner logic 
## functions, and any output files from any of the foregoing 
## (including device programming or simulation files), and any 
## associated documentation or information are expressly subject 
## to the terms and conditions of the Altera Program License 
## Subscription Agreement, the Altera Quartus Prime License Agreement,
## the Altera IP License Agreement, or other applicable license
## agreement, including, without limitation, that your use is for
## the sole purpose of programming logic devices manufactured by
## Altera and sold by Altera or its authorized distributors.  Please
## refer to the Altera Software License Subscription Agreements 
## on the Quartus Prime software download page.


## VENDOR  "Intel Corporation"
## PROGRAM "Quartus Prime"
## VERSION "Version 26.1.0 Build 110 03/26/2026 SC Pro Edition"

## DATE    "Fri Oct  2 02:11:45 2026"

##
## DEVICE  "10AX115N4F40E3SG"
##


#**************************************************************
# Time Information
#**************************************************************

set_time_format -unit ns -decimal_places 3



#**************************************************************
# Create Clock
#**************************************************************

create_clock -name {kernel_clk} -period 12.594 -waveform { 0.000 6.297 } [get_ports {clk}]


#**************************************************************
# Create Generated Clock
#**************************************************************



#**************************************************************
# Set Clock Latency
#**************************************************************



#**************************************************************
# Set Clock Uncertainty
#**************************************************************

set_clock_uncertainty -rise_from [get_clocks {kernel_clk}] -rise_to [get_clocks {kernel_clk}]  0.030  
set_clock_uncertainty -rise_from [get_clocks {kernel_clk}] -fall_to [get_clocks {kernel_clk}]  0.030  
set_clock_uncertainty -fall_from [get_clocks {kernel_clk}] -rise_to [get_clocks {kernel_clk}]  0.030  
set_clock_uncertainty -fall_from [get_clocks {kernel_clk}] -fall_to [get_clocks {kernel_clk}]  0.030  


#**************************************************************
# Set Input Delay
#**************************************************************



#**************************************************************
# Set Output Delay
#**************************************************************



#**************************************************************
# Set Clock Groups
#**************************************************************



#**************************************************************
# Set False Path
#**************************************************************



#**************************************************************
# Set Multicycle Path
#**************************************************************



#**************************************************************
# Set Maximum Delay
#**************************************************************



#**************************************************************
# Set Minimum Delay
#**************************************************************



#**************************************************************
# Set Input Transition
#**************************************************************

