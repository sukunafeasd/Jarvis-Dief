"""Repeatable offline regression groups with isolated data and temporary captures."""
import argparse
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
CORE='''test_command_chaos_round test_command_races_round2 test_command_delivery_round
test_protocol_commands test_protocol_natural_language test_protocol_voice_context_round
test_forge_backend test_forge_host_routing test_forge_snapshot_fence test_forge_status
test_ultron_integration test_ultron_state_regressions test_ultron_host_contract
test_connection_transaction_round2 test_connection_storage test_connections
test_config_atomic_round2 test_data_integrity_round2 test_connection_sound_lifecycle
test_live_pins test_live_presentation_refresh test_daily_refresh_contract
test_refresh_optout_round2 test_refresh_partial_sources test_refresh_monitor_recovery
test_fish_playback test_voice_interrupt test_voice_bugfix_round test_voice_stream_boundaries
test_memory_recall_behavior test_neural_memory test_memory_voice_routing test_system_memory
test_system_stress_round test_failure_recovery_stress test_idle_work_round
test_mode_lifecycle_round test_visual_mode_resume_round test_runtime_recovery_round2
test_background_mode_guards test_adaptive_personality test_calendar_autostart_round
test_round3_mode_connection_lifecycle test_round4_voice_daily test_round4_calendar_source test_transcript_replay_round4
test_contact_voice_round3 test_followup_state_round test_presentation_state_gap
test_briefing_narration test_interface_verification test_forge_project_lookup test_search_locale
test_round5_pin_storage test_round5_forge_state test_round5_settings_transactions test_round6_background_lifecycle test_round7_conversation_intent test_round8_context_outcomes test_round9_domain_guidance test_round10_conditional_commands test_round11_natural_domains test_round12_operation_followup test_round13_spoken_style test_spectro test_spectro_complete
test_connections_and_pins_repair test_free_pins_theme test_settings_connections test_settings_hub test_panel_sound_preference test_spectro_reinforcement test_spectro_continuous_round'''.split()
VISUAL='test_hologram_polish test_holographic_motion test_motion_latency_round test_render_stress_round test_presentation_sync_contract'.split()
CORE.extend(['test_intelligence_evolution','test_intelligence_language_corpus','test_memory_topic_continuity','test_spatial_distribution_repair','test_semantic_index_integrity'])
CORE.append('test_operation_continuity_guard')
CORE.append('test_contextual_decision_round')
CORE.append('test_evidence_coverage')
CORE.append('test_reference_grounding_round')
CORE.append('test_dispatch_evidence')
CORE.append('test_recovery_diagnostics')
CORE.extend(['test_integrated_recovery','test_resource_suite','test_resource_completion','test_essential_plugins'])
CORE.extend(['test_update_maintenance','test_official_distribution','test_factory_distribution'])
CORE.append('test_startup_update_speed')
CORE.append('test_entry_redesign')
CORE.append('test_incremental_integrity')


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--visual',action='store_true')
    args=parser.parse_args()
    output=Path(tempfile.mkdtemp(prefix='dief-audit-visual-' if args.visual else 'dief-audit-core-'))
    os.environ['QT_QPA_PLATFORM']='offscreen'
    os.environ['DIEF_JARVIS_DATA_DIR']=str(output/'data')
    sys.path[:0]=[str(ROOT),str(ROOT/'tests')]
    names=VISUAL if args.visual else CORE
    missing=[name for name in names if not (ROOT/'tests'/(name+'.py')).is_file()]
    if missing:raise RuntimeError('Missing audit modules: '+', '.join(missing))
    suite=unittest.defaultTestLoader.loadTestsFromNames(['tests.'+name for name in names])
    print('Audit output: '+str(output),flush=True)
    captures=output/'captures';captures.mkdir()
    from playwright._impl import _page
    original_capture=_page.async_writefile
    original_text=Path.write_text
    async def capture(path,data):await original_capture(captures/Path(path).name,data)
    def metrics(path,data,*a,**kw):
        target=output/path.name if path.name=='hologram-metrics.json' else path
        return original_text(target,data,*a,**kw)
    with (output/'tests.log').open('w',encoding='utf-8') as log:
        with patch.object(_page,'async_writefile',capture),patch.object(Path,'write_text',metrics):
            result=unittest.TextTestRunner(stream=log,verbosity=2).run(suite)
    report={'passed':result.wasSuccessful(),'tests':result.testsRun,'skipped':len(result.skipped),
            'failures':[(str(test),error) for test,error in result.failures],
            'errors':[(str(test),error) for test,error in result.errors],'output':str(output)}
    (output/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False),flush=True)
    return 0 if result.wasSuccessful() else 1


if __name__=='__main__':sys.exit(main())
