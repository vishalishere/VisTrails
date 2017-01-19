###############################################################################
##
## Copyright (C) 2011-2013, NYU-Poly.
## Copyright (C) 2006-2011, University of Utah. 
## All rights reserved.
## Contact: contact@vistrails.org
##
## This file is part of VisTrails.
##
## "Redistribution and use in source and binary forms, with or without 
## modification, are permitted provided that the following conditions are met:
##
##  - Redistributions of source code must retain the above copyright notice, 
##    this list of conditions and the following disclaimer.
##  - Redistributions in binary form must reproduce the above copyright 
##    notice, this list of conditions and the following disclaimer in the 
##    documentation and/or other materials provided with the distribution.
##  - Neither the name of the University of Utah nor the names of its 
##    contributors may be used to endorse or promote products derived from 
##    this software without specific prior written permission.
##
## THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" 
## AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, 
## THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR 
## PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR 
## CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, 
## EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, 
## PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; 
## OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, 
## WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR 
## OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF 
## ADVISED OF THE POSSIBILITY OF SUCH DAMAGE."
##
###############################################################################

from vistrails.db.versions.common.bundle import SaveBundle
from vistrails.db.versions.common.translate import ExternalData, \
    GroupExternalData, LocalTranslateDictExtdata
from vistrails.db.versions.v2_0_0.domain import DBVistrail, \
    DBWorkflow, DBLog, DBRegistry, DBStartup, DBMashuptrail, DBAction, \
    DBAdd, DBChange, DBDelete, DBAbstraction, DBGroup, DBActionAnnotation, \
    DBModule, DBAnnotation, DBPortSpec, DBPortSpecItem, DBVistrailVariable, \
    IdScope

import copy
import unittest

# 1. we probably have to worry about groups, right? or not?
# 2. what to do about ids that span log and vistrail??

# id_scope = None

def translateVistrail(_vistrail, external_data=None):
    if external_data is None:
        external_data = GroupExternalData()
    with LocalTranslateDictExtdata(external_data) as extdata:
        if (DBAction.vtType, 0) not in extdata.id_remap:
            extdata.id_remap[(DBAction.vtType, 0)] = DBVistrail.ROOT_VERSION

        # fix PortSpecItem ids -- should be unique
        psi_ids = set()
        for action in _vistrail.db_actions:
            for op in action.db_operations:
                if (op.db_what == DBPortSpec.vtType and
                        (op.vtType == DBAdd.vtType or op.vtType == DBChange.vtType)):
                    ps = op.db_data
                    for psi in ps.db_portSpecItems:
                        # only reassign when necessary (helps with translations)
                        if psi.db_id in psi_ids:
                            # we don't need to worry about remaps since psi ids are
                            # not referenced as individual entities
                            while True:
                                new_id = _vistrail.idScope.getNewId(DBPortSpecItem.vtType)
                                if new_id not in psi_ids:
                                    break
                            psi.db_id = new_id
                        psi_ids.add(psi.db_id)

        vistrail = DBVistrail()
        id_scope = vistrail.idScope

        def update_workflow(old_obj, trans_dict):
            group_extdata = extdata.get_child_extdata(('group', old_obj.db_id),
                                                      True, GroupExternalData)
            with LocalTranslateDictExtdata(group_extdata) as g_extdata:
                group_extdata.update_tdict(extdata)
                workflow = translateWorkflow(old_obj.db_workflow, g_extdata)
            return workflow

        session_remap = {}
        def update_session(old_obj, trans_dict):
            if old_obj.db_session is None:
                return ''
            if old_obj.db_session in session_remap:
                return session_remap[old_obj.db_session]
            else:
                new_id = id_scope.getNewId() # doesn't matter what objType is
                session_remap[old_obj.db_session] = new_id
                return new_id

        extdata.add_translator('DBGroup', 'workflow', update_workflow)
        extdata.add_translator('DBAction', 'session', update_session)
        if not external_data.has_translator('DBAbstraction', 'internal_version'):
            def update_internal_version(old_obj, trans_dict):
                """This is bogus since we must use translateBundle and its
                internal_version logic in general but works for testing"""
                iv_key = ('abs_internal_version', old_obj.db_internal_version)
                if iv_key in extdata.id_remap:
                    return extdata.id_remap[iv_key]
                else:
                    new_id = id_scope.getNewId('abs_internal_version')
                    extdata.id_remap[iv_key] = new_id
                    return new_id
            extdata.add_translator('DBAbstraction', 'internal_version',
                                      update_internal_version)
        vistrail = DBVistrail.update_version(_vistrail,
                                             extdata.translate_dict, vistrail)
        for action in vistrail.db_actions:
            for pos, op in enumerate(action.db_operations):
                op.db_pos = pos
        # FIXME have to eventually expand the inner workflows and update their ids
        vistrail = vistrail.do_copy(True, id_scope, extdata.id_remap)

        # remap upgrade annotations
        for ann in vistrail.db_actionAnnotations[:]:
            if ann.db_key == "__upgrade__": # vistrails.core.vistrail.vistrail.Vistrail.UPDATE_ANNOTATION
                vistrail.db_delete_actionAnnotation(ann)
                ann.db_value = "%s" % extdata.id_remap[(DBAction.vtType, long(ann.db_value))]
                vistrail.db_add_actionAnnotation(ann)

        # don't want to re-id vistrail variables; they already have a uuid
        # if we don't do this, xml works fine, but sql is problematic because
        # remapped uuids are ints stored as strings...
        inv_remap = {(t, k2): k1 for (t, k1), k2 in extdata.id_remap.iteritems()}
        for vv in vistrail.db_vistrailVariables:
            if (DBVistrailVariable.vtType, vv.db_uuid) in inv_remap:
                vv.db_uuid = inv_remap[(DBVistrailVariable.vtType, vv.db_uuid)]

    vistrail.db_version = '2.0.0'
    return vistrail

def translateWorkflow(_workflow, external_data=None):
    if external_data is None:
        external_data = GroupExternalData()
    with LocalTranslateDictExtdata(external_data) as extdata:

        def update_workflow(old_obj, trans_dict):
            group_extdata = extdata.get_child_extdata(('group', old_obj.db_id),
                                                      True, GroupExternalData)
            with LocalTranslateDictExtdata(group_extdata) as g_extdata:
                group_extdata.update_tdict(extdata)
                workflow = translateWorkflow(old_obj.db_workflow, g_extdata)
            return workflow

        # if 'DBGroup' not in translate_dict:
        #     translate_dict['DBGroup'] = {'workflow': update_workflow}
        extdata.add_translator('DBGroup', 'workflow', update_workflow)

        workflow = DBWorkflow()
        id_scope = IdScope(remap={DBAbstraction.vtType: DBModule.vtType, DBGroup.vtType: DBModule.vtType})
        workflow = DBWorkflow.update_version(_workflow, extdata.translate_dict, workflow)
        workflow = workflow.do_copy(True, id_scope, extdata.id_remap)
    workflow.db_version = '2.0.0'
    return workflow

def translateLog(_log, external_data=None):
    if external_data is None:
        external_data = ExternalData()
    with LocalTranslateDictExtdata(external_data) as extdata:
        log = DBLog()
        id_scope = log.id_scope
        log = DBLog.update_version(_log, extdata.translate_dict, log)
        log = log.do_copy(True, id_scope, extdata.id_remap)
    log.db_version = '2.0.0'
    return log

def translateRegistry(_registry, external_data=None):
    if external_data is None:
        external_data = ExternalData()
    with LocalTranslateDictExtdata(external_data) as extdata:
        registry = DBRegistry()
        id_scope = registry.id_scope
        registry = DBRegistry.update_version(_registry, extdata.translate_dict, registry)
        registry = registry.do_copy(True, id_scope, extdata.id_remap)
    registry.db_version = '2.0.0'
    return registry

def translateMashup(_mashup, external_data=None):
    #FIXME check if this is correct
    if external_data is None:
        external_data = ExternalData()
    with LocalTranslateDictExtdata(external_data) as extdata:
        mashup = DBMashuptrail()
        id_scope = mashup.id_scope
        mashup = DBMashuptrail.update_version(_mashup, extdata.translate_dict, mashup)
        mashup = mashup.do_copy(True, id_scope, extdata.id_remap)
    mashup.db_version = '2.0.0'
    return mashup

def translateStartup(_startup, external_data=None):
    startup = DBStartup()
    translate_dict = {}
    startup = DBStartup.update_version(_startup, translate_dict, startup)

    startup.db_version = '2.0.0'
    return startup

def translateBundle(_bundle, external_data=None):
    if external_data is None:
        external_data = ExternalData()
    with LocalTranslateDictExtdata(external_data) as extdata:
        bundle_contents = {}
        # abstractions need to be translated first so internal versions in the
        # vistrail match up...

        # actual objects are translated in subworkflows field
        # will be serialized in vistrails.db.services.io
        abstractions = []
        for _abstraction in _bundle.abstractions:
            abstractions.append(_abstraction)
        bundle_contents['abstractions'] = abstractions

        # actually translate abstractions here
        subworkflows = []
        subworkflows_extdata = None
        if extdata.has_child_extdata('subworkflows'):
            subworkflows_extdata = extdata.get_child_extdata('subworkflows')
        from vistrails.core.modules.sub_module import parse_abstraction_name
        for _subworkflow in _bundle.subworkflows:
            (path, prefix, abs_name, abs_namespace, suffix) = \
                parse_abstraction_name(_subworkflow.db_abstraction_fname, True)
            subwf_key = (abs_name, abs_namespace)
            subwf_extdata = extdata.get_child_extdata(('subworkflow', subwf_key),
                                                      True, GroupExternalData)
            if subworkflows_extdata is not None:
                subwf_extdata.update(subworkflows_extdata)
            subworkflow = translateVistrail(_subworkflow, subwf_extdata)
            subworkflow.db_abstraction_fname = _subworkflow.db_abstraction_fname
            subworkflows.append(subworkflow)
        bundle_contents['subworkflows'] = subworkflows

        internal_version_remap = {}
        # get all subworkflow extdatas here...
        for subwf_key, subwf_extdata in extdata.child_extdata.iteritems():
            if type(subwf_key) == tuple and subwf_key[0] == 'subworkflow':
                for (t, k), v in subwf_extdata.id_remap.iteritems():
                    if t == DBAction.vtType:
                        internal_version_remap[subwf_key[1] + (str(k),)] = v

        def update_abstraction_iversion(old_obj, trans_dict):
            return internal_version_remap[
                (old_obj.db_name, old_obj.db_namespace,
                 old_obj.db_internal_version)]

        vistrail_extdata = None
        if _bundle.vistrail is not None:
            # need to add the internal version remap to the translate_dict
            vistrail_extdata = extdata.get_child_extdata('vistrail', True,
                                                         GroupExternalData)
            with LocalTranslateDictExtdata(vistrail_extdata) as vt_extdata:
                vt_extdata.add_translator('DBAbstraction', 'internal_version',
                                          update_abstraction_iversion)
                _vistrail = _bundle.vistrail
                vistrail = translateVistrail(_vistrail, vt_extdata)
            bundle_contents['vistrail'] = vistrail

        workflow_extdata = None
        if _bundle.workflow is not None:
            workflow_extdata = extdata.get_child_extdata('workflow', True,
                                                         GroupExternalData)
            with LocalTranslateDictExtdata(workflow_extdata) as wf_extdata:
                vt_extdata.add_translator('DBAbstraction', 'internal_version',
                                          update_abstraction_iversion)
                if vistrail_extdata is not None:
                    vt_remap = vistrail_extdata.remove_non_unique(set())
                    # FIXME allow vistrail to clobber workflow ids?
                    # if materialization is direct, this should be better
                    wf_extdata.update_id_remap(vt_remap)

                _workflow = _bundle.workflow
                workflow = translateWorkflow(_workflow, workflow_extdata)
            bundle_contents['workflow'] = workflow

        if vistrail_extdata is not None:
            core_extdata = copy.copy(vistrail_extdata)
            core_extdata.remove_non_unique(set([DBAnnotation.vtType]), True)
        elif workflow_extdata is not None:
            core_extdata = copy.copy(workflow_extdata)
            core_extdata.remove_non_unique(set(), True)

        mashups = []
        mashups_extdata = extdata.get_child_extdata('mashups', True)
        mashups_extdata.update(core_extdata)
        for _mashup in _bundle.mashups:
            mashup_extdata = \
                extdata.get_child_extdata(('mashup', _mashup.db_id), True)
            mashup_extdata.update(mashups_extdata)
            mashup = translateMashup(_mashup, mashup_extdata)
            mashups.append(mashup)
        bundle_contents['mashups'] = mashups

        # FIXME abstractions and mashups may affect log
        if _bundle.log is not None:
            log_extdata = external_data.get_child_extdata('log', True)
            log_extdata.update_id_remap(core_extdata)
            _log = _bundle.log
            log = translateLog(_log, log_extdata)
            bundle_contents['log'] = log

        if _bundle.registry is not None:
            registry_extdata = external_data.get_child_extdata('registry', True)
            _registry = _bundle.registry
            registry = translateRegistry(_registry, registry_extdata)
            bundle_contents['registry'] = registry

        # done with local bundle extdata
    # FIXME set version in bundle
    return SaveBundle(_bundle.bundle_type,
                      **bundle_contents)