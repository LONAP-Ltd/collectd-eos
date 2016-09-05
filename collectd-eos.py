# Copyright (c) 2013, Arista Networks, Inc. 
# All rights reserved. 
# 
# Redistribution and use in source and binary forms, with or without 
# modification, are permitted provided that the following conditions are 
# met: 
# - Redistributions of source code must retain the above copyright notice, 
# this list of conditions and the following disclaimer. 
# - Redistributions in binary form must reproduce the above copyright 
# notice, this list of conditions and the following disclaimer in the 
# documentation and/or other materials provided with the distribution. 
# - Neither the name of Arista Networks nor the names of its 
# contributors may be used to endorse or promote products derived from 
# this software without specific prior written permission. 
# 
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS 
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT 
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR 
# A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL ARISTA NETWORKS 
# BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR 
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF 
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR 
# BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, 
# WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE 
# OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN 
# IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE. #
#
# collect-eos.py
#
#    Version 1.0 17/12/2013
#    Written by:
#       Sean Flack (sean@aristanetworks.com)
#
#    Revision history:
#       1.0 - initial release

'''
   DESCRIPTION
   This script should be used in conjunction with Collectd for EOS and enables
   the collection of various switch metrics via the Arista Command-API.

   INSTALLATION
   After altering this file, it should be placed in:
   /opt/collect/python/

   CONFIGURATION
   Not Applicable

   COMPATIBILITY
   Tested with EOS v4.13.0F

   LIMITATIONS
   None Known.

'''

import collectd
import ssl
from pprint import pprint
from jsonrpclib import Server
switch = {}
platform = ''
hosts = []
#username = 'foobar'
#password = 'foobar'


ssl._create_default_https_context = ssl._create_unverified_context

#== Our Own Functions go here: ==#
def configer(ObjConfiguration):
    global username
    global password
    collectd.debug('Configuring Stuff')
    for node in ObjConfiguration.children:
        key = node.key.lower()
        val = node.values[0]
        if key == 'host':
            hosts.append(val)
            collectd.error('collectd-eos plugin: using host %s' % val)
        elif key == 'username':
            username = val
        elif key == 'password':
            password = val
        else:
            collectd.error('collectd-eos plugin: Unknown config key: %s' % key)

def initer():
    global switch
    for h in hosts:
        switch[h] = Server( "https://%s:%s@%s/command-api"%(username,password,h) )
        response = switch[h].runCmds( 1, ["show version"] )
        collectd.error( "Switch %s system MAC addess is %s" % (h,response[0]["systemMacAddress"]) )
    
def reader(input_data=None):
    metric = collectd.Values();
    for h in hosts:
        intStats(metric, h)
        intDom(metric, h)
        response = switch[h].runCmds( 1, ["show version"] )
        #Check whether this platform supports LANZ
        global platform
        platform = response[0]["modelName"][ 4:8 ]
        if platform in ('7150', '7124', '7148' ):
            lanzTxLatency(metric, h)
            lanzQueueLength(metric, h)
            lanzDrops(metric, h)
        #vxlanSoftware(metric, h)

def intStats(metric,host):
    intMetric = metric
    response = switch[host].runCmds( 1, ["show interfaces"] )
    for x in response[0]["interfaces"]:
        if "interfaceCounters" not in response[0]["interfaces"][x]: 
            collectd.debug("No counters for %s %s"%(host,x))
            continue
        UcastPkts = [ 0, 0 ]
        BroadcastPkts = [ 0, 0 ]
        MulticastPkts = [ 0, 0 ]
        Discards = [ 0, 0 ]
        Octets = [ 0, 0 ]
        bandwidth = response[0]["interfaces"][x].get("bandwidth")
        Errors = [ 0, 0 ]
        statsBlock = response[0]["interfaces"][x]["interfaceCounters"]
        timeStamp = statsBlock.get("counterRefreshTime")
        for y in statsBlock:
            if y.startswith('in'):
                if y[2:] == 'UcastPkts':
                    UcastPkts[0] = statsBlock[y]
                elif y[2:] == 'BroadcastPkts':
                    BroadcastPkts[0] = statsBlock[y]
                elif y[2:] == 'MulticastPkts':
                    MulticastPkts[0] = statsBlock[y]
                elif y[2:] == 'Discards':
                    Discards[0] = statsBlock[y]
                elif y[2:] == 'Octets':
                    Octets[0] = statsBlock[y]
            if y.startswith('out'):
                if y[3:] == 'UcastPkts':
                    UcastPkts[1] = statsBlock[y]
                elif y[3:] == 'BroadcastPkts':
                    BroadcastPkts[1] = statsBlock[y]
                elif y[3:] == 'MulticastPkts':
                    MulticastPkts[1] = statsBlock[y]
                elif y[3:] == 'Discards':
                    Discards[1] = statsBlock[y]
                elif y[3:] == 'Octets':
                    Octets[1] = statsBlock[y]
            if y == 'totalInErrors':
                    Errors[0] = statsBlock[y]
            if y == 'totalOutErrors':
                    Errors[1] = statsBlock[y]
        collectd.debug("Stats %s %s %f %i %i"%(host,x, timeStamp, Octets[0], Octets[1]))

        #Dispatch the metrics
        intMetric.host = host
        intMetric.plugin = 'eos'
        intMetric.plugin_instance = x
        intMetric.time = timeStamp
        intMetric.values = (bandwidth,)
        intMetric.type = 'eos_if_Bandwidth'
        intMetric.dispatch()
        intMetric.values = BroadcastPkts
        intMetric.type = 'eos_if_BroadcastPkts'
        intMetric.dispatch()
        intMetric.values = UcastPkts
        intMetric.type = 'eos_if_UcastPkts'
        intMetric.dispatch()
        intMetric.values = MulticastPkts
        intMetric.type = 'eos_if_MulticastPkts'
        intMetric.dispatch()
        intMetric.values = Discards
        intMetric.type = 'eos_if_Discards'
        intMetric.dispatch()
        intMetric.values = Octets
        intMetric.type = 'eos_if_Octets'
        intMetric.dispatch()
        intMetric.values = Errors
        intMetric.type = 'eos_if_Errors'
        intMetric.dispatch()

def intDom(metric,host):
    intMetric = metric
    response = switch[host].runCmds( 1, ["show interfaces transceiver"] )
    for x in response[0]["interfaces"]:
        intMetric.host = host
        intMetric.plugin = 'eos'
        intMetric.plugin_instance = x
        for y in response[0]["interfaces"][x]:
            if y not in [ 'updateTime', 'vendorSn', 'mediaType','narrowBand' ]:
                intMetric.type = 'eos_dom_%s' % y
                intMetric.values = [ response[0]["interfaces"][x][y] ]
                intMetric.dispatch()

def lanzTxLatency(metric,host):
    intMetric = metric
    response = switch[host].runCmds( 1, ["show queue-monitor length limit 10 seconds tx-latency"] )
    #Check whether this platform is a 7150
    if platform == '7150':
		for x in response[0]["entryList"]:
                        intMetric.host = host
                        intMetric.plugin = 'eos'
			intMetric.plugin_instance = x["interface"]
			intMetric.type = 'eos_lanz_txLatency'
			intMetric.type_instance = 'trafficClass-%s' % x["trafficClass"]
			intMetric.time = x["entryTime"]
			intMetric.values = [ x["txLatency"] ]
			intMetric.dispatch()
        
def lanzQueueLength(metric,host):
    intMetric = metric
    response = switch[host].runCmds( 1, ["show queue-monitor length limit 10 seconds"] )
    #Check whether this platform is a 7150
    if platform == '7150':
		for x in response[0]["entryList"]:
			if x["entryType"] == 'U':
                                intMetric.host = host
                                intMetric.plugin = 'eos'
				#intMetric.plugin = 'eos-lanz'
				intMetric.plugin_instance = x["interface"]
				intMetric.type = 'eos_lanz_queueLength'
				intMetric.type_instance = 'trafficClass-%s' % x["trafficClass"]
				intMetric.time = x["entryTime"]
				intMetric.values = [ x["queueLength"] ]
				intMetric.dispatch()
            
def lanzDrops(metric,host):
    intMetric = metric
    response = switch[host].runCmds( 1, ["show queue-monitor length limit 10 seconds drops"] )
    #Check whether this platform is a 7150
    if platform == '7150':
		for x in response[0]["entryList"]:
                        intMetric.host = host
                        intMetric.plugin = 'eos'
			intMetric.plugin_instance = x["interface"]
			intMetric.type = 'eos_lanz_txDrops'
			intMetric.time = x["entryTime"]
			intMetric.values = [ x["txDrops"] ]
			intMetric.dispatch()

def vxlanSoftware(metric,host):
    intMetric = metric
    response = switch[host].runCmds( 1, ["show vxlan counters software"] )
    vxlanCounters = response[0]['vxlanCounters']
    intMetric.host = host
    intMetric.plugin = 'eos'
    intMetric.plugin_instance = 'vxlanSoftware'
    for a in vxlanCounters:
        collectd.error( "Switch %s BLAH %s" % (host,a))
    for m in ['decapPkts', 'decapBytes', 'encapTimeout', 'encapReadErr', 'encapSendErr', 'encapBytes', 'encapPkts']:
        if m in vxlanCounters: 
            collectd.error( "Switch %s processing %s" % (host,m))
            intMetric.type = 'eos_' + m
            intMetric.values = [ vxlanCounters[m] ]
            intMetric.dispatch()

#== Hook Callbacks, Order is important! ==#
collectd.register_config(configer)
collectd.register_init(initer)
collectd.register_read(reader)

