from __future__ import annotations

import argparse
import json
import sys

from .bootstrap_graph import build_bootstrap_graph
from .command_graph import build_command_graph
from .commands import execute_command, get_command, get_commands, render_command_index
from .direct_modes import run_deep_link, run_direct_connect
from .parity_audit import run_parity_audit
from .permissions import ToolPermissionContext
from .port_manifest import build_port_manifest
from .query_engine import QueryEnginePort
from .remote_runtime import run_remote_mode, run_ssh_mode, run_teleport_mode
from .runtime import PortRuntime
from .session_store import load_session
from .setup import run_setup
from .tool_pool import assemble_tool_pool
from .tools import execute_tool, get_tool, get_tools, render_tool_index
from .services import CycodeSystemService, CycodeInferenceService, CycodeAdminService
from .replLauncher import launch_startup_screen


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='CyCode — AI coding assistant powered by CygnisAI')
    subparsers = parser.add_subparsers(dest='command', required=True)

    # ── Startup screen ──
    startup_parser = subparsers.add_parser('startup', help='display the CyCode startup / welcome screen')
    startup_parser.add_argument('--api-key', default=None, help='CygnisAI API key')
    startup_parser.add_argument('--no-probe', action='store_true', help='skip live API probe')

    # ── Interactive REPL ──
    repl_parser = subparsers.add_parser('repl', help='launch interactive CyCode REPL (equivalent of claude)')
    repl_parser.add_argument('--api-key', default=None, help='CygnisAI API key')
    repl_parser.add_argument('--model', default=None, help='model to use')
    repl_parser.add_argument('--no-stream', action='store_true', help='disable streaming')
    repl_parser.add_argument('--no-banner', action='store_true', help='skip startup banner')
    repl_parser.add_argument('--file', default=None, help='inject file into initial context')

    # ── One-shot chat ──
    chat_parser = subparsers.add_parser('chat', help='one-shot chat prompt (non-interactive)')
    chat_parser.add_argument('prompt', help='prompt text')
    chat_parser.add_argument('--api-key', default=None, help='CygnisAI API key')
    chat_parser.add_argument('--model', default=None, help='model to use')
    chat_parser.add_argument('--no-stream', action='store_true', help='disable streaming')
    chat_parser.add_argument('--file', default=None, help='inject file into context')

    # Existing commands...
    subparsers.add_parser('summary', help='render a Markdown summary of the Python porting workspace')
    subparsers.add_parser('manifest', help='print the current Python workspace manifest')
    subparsers.add_parser('parity-audit', help='compare the Python workspace against the local ignored TypeScript archive when available')
    subparsers.add_parser('setup-report', help='render the startup/prefetch setup report')
    subparsers.add_parser('command-graph', help='show command graph segmentation')
    subparsers.add_parser('tool-pool', help='show assembled tool pool with default settings')
    subparsers.add_parser('bootstrap-graph', help='show the mirrored bootstrap/runtime graph stages')
    list_parser = subparsers.add_parser('subsystems', help='list the current Python modules in the workspace')
    list_parser.add_argument('--limit', type=int, default=32)

    commands_parser = subparsers.add_parser('commands', help='list mirrored command entries from the archived snapshot')
    commands_parser.add_argument('--limit', type=int, default=20)
    commands_parser.add_argument('--query')
    commands_parser.add_argument('--no-plugin-commands', action='store_true')
    commands_parser.add_argument('--no-skill-commands', action='store_true')

    tools_parser = subparsers.add_parser('tools', help='list mirrored tool entries from the archived snapshot')
    tools_parser.add_argument('--limit', type=int, default=20)
    tools_parser.add_argument('--query')
    tools_parser.add_argument('--simple-mode', action='store_true')
    tools_parser.add_argument('--no-mcp', action='store_true')
    tools_parser.add_argument('--deny-tool', action='append', default=[])
    tools_parser.add_argument('--deny-prefix', action='append', default=[])

    route_parser = subparsers.add_parser('route', help='route a prompt across mirrored command/tool inventories')
    route_parser.add_argument('prompt')
    route_parser.add_argument('--limit', type=int, default=5)

    bootstrap_parser = subparsers.add_parser('bootstrap', help='build a runtime-style session report from the mirrored inventories')
    bootstrap_parser.add_argument('prompt')
    bootstrap_parser.add_argument('--limit', type=int, default=5)

    loop_parser = subparsers.add_parser('turn-loop', help='run a small stateful turn loop for the mirrored runtime')
    loop_parser.add_argument('prompt')
    loop_parser.add_argument('--limit', type=int, default=5)
    loop_parser.add_argument('--max-turns', type=int, default=3)
    loop_parser.add_argument('--structured-output', action='store_true')

    flush_parser = subparsers.add_parser('flush-transcript', help='persist and flush a temporary session transcript')
    flush_parser.add_argument('prompt')

    load_session_parser = subparsers.add_parser('load-session', help='load a previously persisted session')
    load_session_parser.add_argument('session_id')

    # Remote modes...
    remote_parser = subparsers.add_parser('remote-mode', help='simulate remote-control runtime branching')
    remote_parser.add_argument('target')
    ssh_parser = subparsers.add_parser('ssh-mode', help='simulate SSH runtime branching')
    ssh_parser.add_argument('target')
    teleport_parser = subparsers.add_parser('teleport-mode', help='simulate teleport runtime branching')
    teleport_parser.add_argument('target')
    direct_parser = subparsers.add_parser('direct-connect-mode', help='simulate direct-connect runtime branching')
    direct_parser.add_argument('target')
    deep_link_parser = subparsers.add_parser('deep-link-mode', help='simulate deep-link runtime branching')
    deep_link_parser.add_argument('target')

    show_command = subparsers.add_parser('show-command', help='show one mirrored command entry by exact name')
    show_command.add_argument('name')
    show_tool = subparsers.add_parser('show-tool', help='show one mirrored tool entry by exact name')
    show_tool.add_argument('name')

    exec_command_parser = subparsers.add_parser('exec-command', help='execute a mirrored command shim by exact name')
    exec_command_parser.add_argument('name')
    exec_command_parser.add_argument('prompt')

    exec_tool_parser = subparsers.add_parser('exec-tool', help='execute a mirrored tool shim by exact name')
    exec_tool_parser.add_argument('name')
    exec_tool_parser.add_argument('payload')

    # Cycode System commands
    subparsers.add_parser('cy-info', help='get Cycode server info')
    subparsers.add_parser('cy-health', help='get Cycode health status')
    subparsers.add_parser('cy-models', help='list available Cycode models')
    model_details_parser = subparsers.add_parser('cy-model-details', help='get details for a specific model')
    model_details_parser.add_argument('id', help='model ID')
    subparsers.add_parser('cy-loadtest-run', help='run a Cycode load test')
    subparsers.add_parser('cy-loadtest-status', help='get Cycode load test status')

    # Cycode Inference (Chat) commands
    chat_parser = subparsers.add_parser('cy-chat', help='send a chat message to Cycode API')
    chat_parser.add_argument('prompt', help='the user prompt')
    chat_parser.add_argument('--api-key', help='Cycode API key')
    chat_parser.add_argument('--target', default='auto', help='the target (default: auto)')
    chat_parser.add_argument('--max-tokens', type=int, default=512, help='max new tokens (default: 512)')
    chat_parser.add_argument('--session-id', help='session ID')
    chat_parser.add_argument('--messages', help='JSON string of messages')
    chat_parser.add_argument('--no-memory', action='store_false', dest='use_memory', help='disable memory')

    chat_stream_parser = subparsers.add_parser('cy-chat-stream', help='stream a chat message from Cycode API')
    chat_stream_parser.add_argument('prompt', help='the user prompt')
    chat_stream_parser.add_argument('--api-key', help='Cycode API key')
    chat_stream_parser.add_argument('--target', default='auto', help='the target (default: auto)')
    chat_stream_parser.add_argument('--max-tokens', type=int, default=512, help='max new tokens (default: 512)')
    chat_stream_parser.add_argument('--session-id', help='session ID')
    chat_stream_parser.add_argument('--messages', help='JSON string of messages')
    chat_stream_parser.add_argument('--no-memory', action='store_false', dest='use_memory', help='disable memory')

    chat_history_parser = subparsers.add_parser('cy-chat-history', help='get chat history from Cycode API')
    chat_history_parser.add_argument('--api-key', help='Cycode API key')

    chat_history_item_parser = subparsers.add_parser('cy-chat-history-item', help='get a specific chat history item')
    chat_history_item_parser.add_argument('id', help='the history item ID')
    chat_history_item_parser.add_argument('--api-key', help='Cycode API key')

    # Cycode Session commands
    create_session_parser = subparsers.add_parser('cy-session-create', help='create a new Cycode session')
    create_session_parser.add_argument('--api-key', help='Cycode API key')

    list_sessions_parser = subparsers.add_parser('cy-session-list', help='list active Cycode sessions')
    list_sessions_parser.add_argument('--api-key', help='Cycode API key')

    session_details_parser = subparsers.add_parser('cy-session-details', help='get details of a Cycode session')
    session_details_parser.add_argument('id', help='session ID')
    session_details_parser.add_argument('--api-key', help='Cycode API key')

    add_session_message_parser = subparsers.add_parser('cy-session-add-message', help='add a message to a Cycode session')
    add_session_message_parser.add_argument('id', help='session ID')
    add_session_message_parser.add_argument('role', choices=['user', 'assistant', 'system'], help='message role')
    add_session_message_parser.add_argument('content', help='message content')
    add_session_message_parser.add_argument('--api-key', help='Cycode API key')

    # CyVision commands
    img_gen_parser = subparsers.add_parser('cy-img-generate', help='generate an image from prompt')
    img_gen_parser.add_argument('prompt', help='image description')
    img_gen_parser.add_argument('--quality', default='standard', help='image quality')
    img_gen_parser.add_argument('--api-key', help='Cycode API key')

    img_edit_parser = subparsers.add_parser('cy-img-edit', help='edit an existing image')
    img_edit_parser.add_argument('image_path', help='path to local image file')
    img_edit_parser.add_argument('prompt', help='editing instructions')
    img_edit_parser.add_argument('--api-key', help='Cycode API key')

    img_analyze_parser = subparsers.add_parser('cy-img-analyze', help='analyze an image content')
    img_analyze_parser.add_argument('image_path', help='path to local image file')
    img_analyze_parser.add_argument('--api-key', help='Cycode API key')

    # Code commands
    code_exec_parser = subparsers.add_parser('cy-code-execute', help='execute code in sandbox')
    code_exec_parser.add_argument('code', help='the code to execute')
    code_exec_parser.add_argument('--lang', default='python', help='programming language')
    code_exec_parser.add_argument('--timeout', type=int, default=30, help='execution timeout in seconds')
    code_exec_parser.add_argument('--api-key', help='Cycode API key')

    code_analyze_parser = subparsers.add_parser('cy-code-analyze', help='analyze code quality')
    code_analyze_parser.add_argument('code', help='the code to analyze')
    code_analyze_parser.add_argument('--api-key', help='Cycode API key')

    code_refactor_parser = subparsers.add_parser('cy-code-refactor', help='refactor code')
    code_refactor_parser.add_argument('code', help='the code to refactor')
    code_refactor_parser.add_argument('--api-key', help='Cycode API key')

    # Cycode Admin commands
    auth_status_parser = subparsers.add_parser('cy-auth-status', help='check API key status')
    auth_status_parser.add_argument('--api-key', help='Cycode API key')

    create_key_parser = subparsers.add_parser('cy-key-create', help='create a new API key')
    create_key_parser.add_argument('label', help='label for the new key')
    create_key_parser.add_argument('--admin-key', required=True, help='Admin API key')

    list_keys_parser = subparsers.add_parser('cy-key-list', help='list API keys')
    list_keys_parser.add_argument('--admin-key', required=True, help='Admin API key')

    delete_key_parser = subparsers.add_parser('cy-key-delete', help='delete an API key')
    delete_key_parser.add_argument('label', help='label of the key to delete')
    delete_key_parser.add_argument('--admin-key', required=True, help='Admin API key')

    # Queue commands
    list_jobs_parser = subparsers.add_parser('cy-queue-list', help='list queue jobs')
    list_jobs_parser.add_argument('--api-key', help='Cycode API key')

    job_status_parser = subparsers.add_parser('cy-queue-status', help='get job status')
    job_status_parser.add_argument('id', help='job ID')
    job_status_parser.add_argument('--api-key', help='Cycode API key')

    # Ops commands
    logs_parser = subparsers.add_parser('cy-logs', help='get server logs')
    logs_parser.add_argument('--admin-key', required=True, help='Admin API key')

    usage_metrics_parser = subparsers.add_parser('cy-metrics-usage', help='get usage metrics')
    usage_metrics_parser.add_argument('--api-key', help='Cycode API key')

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    manifest = build_port_manifest()
    
    # Generic services initialization helper
    api_key = getattr(args, 'api_key', None)
    admin_key = getattr(args, 'admin_key', None)
    
    system_service = CycodeSystemService(api_key=api_key, admin_key=admin_key)
    inference_service = CycodeInferenceService(api_key=api_key, admin_key=admin_key)
    admin_service = CycodeAdminService(api_key=api_key, admin_key=admin_key)

    if args.command == 'startup':
        launch_startup_screen(
            api_key=getattr(args, 'api_key', None) or api_key,
            probe=not getattr(args, 'no_probe', False),
        )
        return 0

    if args.command == 'repl':
        from .cycode_cli import main as cli_main
        argv = []
        if getattr(args, 'api_key', None):
            argv += ['--api-key', args.api_key]
        if getattr(args, 'model', None):
            argv += ['--model', args.model]
        if getattr(args, 'no_stream', False):
            argv.append('--no-stream')
        if getattr(args, 'no_banner', False):
            argv.append('--no-banner')
        if getattr(args, 'file', None):
            argv += ['--file', args.file]
        return cli_main(argv)

    if args.command == 'chat':
        from .cycode_cli import main as cli_main
        argv = [args.prompt, '--print']
        if getattr(args, 'api_key', None):
            argv += ['--api-key', args.api_key]
        if getattr(args, 'model', None):
            argv += ['--model', args.model]
        if getattr(args, 'no_stream', False):
            argv.append('--no-stream')
        if getattr(args, 'file', None):
            argv += ['--file', args.file]
        return cli_main(argv)

    if args.command == 'summary':
        print(QueryEnginePort(manifest).render_summary())
        return 0
    if args.command == 'manifest':
        print(manifest.to_markdown())
        return 0
    if args.command == 'parity-audit':
        print(run_parity_audit().to_markdown())
        return 0
    if args.command == 'setup-report':
        print(run_setup().as_markdown())
        return 0
    if args.command == 'command-graph':
        print(build_command_graph().as_markdown())
        return 0
    if args.command == 'tool-pool':
        print(assemble_tool_pool().as_markdown())
        return 0
    if args.command == 'bootstrap-graph':
        print(build_bootstrap_graph().as_markdown())
        return 0
    if args.command == 'subsystems':
        for subsystem in manifest.top_level_modules[: args.limit]:
            print(f'{subsystem.name}\t{subsystem.file_count}\t{subsystem.notes}')
        return 0
    if args.command == 'commands':
        if args.query:
            print(render_command_index(limit=args.limit, query=args.query))
        else:
            commands = get_commands(include_plugin_commands=not args.no_plugin_commands, include_skill_commands=not args.no_skill_commands)
            output_lines = [f'Command entries: {len(commands)}', '']
            output_lines.extend(f'- {module.name} — {module.source_hint}' for module in commands[: args.limit])
            print('\n'.join(output_lines))
        return 0
    if args.command == 'tools':
        if args.query:
            print(render_tool_index(limit=args.limit, query=args.query))
        else:
            permission_context = ToolPermissionContext.from_iterables(args.deny_tool, args.deny_prefix)
            tools = get_tools(simple_mode=args.simple_mode, include_mcp=not args.no_mcp, permission_context=permission_context)
            output_lines = [f'Tool entries: {len(tools)}', '']
            output_lines.extend(f'- {module.name} — {module.source_hint}' for module in tools[: args.limit])
            print('\n'.join(output_lines))
        return 0
    if args.command == 'route':
        matches = PortRuntime().route_prompt(args.prompt, limit=args.limit)
        if not matches:
            print('No mirrored command/tool matches found.')
            return 0
        for match in matches:
            print(f'{match.kind}\t{match.name}\t{match.score}\t{match.source_hint}')
        return 0
    if args.command == 'bootstrap':
        print(PortRuntime().bootstrap_session(args.prompt, limit=args.limit).as_markdown())
        return 0
    if args.command == 'turn-loop':
        results = PortRuntime().run_turn_loop(args.prompt, limit=args.limit, max_turns=args.max_turns, structured_output=args.structured_output)
        for idx, result in enumerate(results, start=1):
            print(f'## Turn {idx}')
            print(result.output)
            print(f'stop_reason={result.stop_reason}')
        return 0
    if args.command == 'flush-transcript':
        engine = QueryEnginePort.from_workspace()
        engine.submit_message(args.prompt)
        path = engine.persist_session()
        print(path)
        print(f'flushed={engine.transcript_store.flushed}')
        return 0
    if args.command == 'load-session':
        session = load_session(args.session_id)
        print(f'{session.session_id}\n{len(session.messages)} messages\nin={session.input_tokens} out={session.output_tokens}')
        return 0
    if args.command == 'remote-mode':
        print(run_remote_mode(args.target).as_text())
        return 0
    if args.command == 'ssh-mode':
        print(run_ssh_mode(args.target).as_text())
        return 0
    if args.command == 'teleport-mode':
        print(run_teleport_mode(args.target).as_text())
        return 0
    if args.command == 'direct-connect-mode':
        print(run_direct_connect(args.target).as_text())
        return 0
    if args.command == 'deep-link-mode':
        print(run_deep_link(args.target).as_text())
        return 0
    if args.command == 'show-command':
        module = get_command(args.name)
        if module is None:
            print(f'Command not found: {args.name}')
            return 1
        print('\n'.join([module.name, module.source_hint, module.responsibility]))
        return 0
    if args.command == 'show-tool':
        module = get_tool(args.name)
        if module is None:
            print(f'Tool not found: {args.name}')
            return 1
        print('\n'.join([module.name, module.source_hint, module.responsibility]))
        return 0
    if args.command == 'exec-command':
        result = execute_command(args.name, args.prompt)
        print(result.message)
        return 0 if result.handled else 1
    if args.command == 'exec-tool':
        result = execute_tool(args.name, args.payload)
        print(result.message)
        return 0 if result.handled else 1
    
    # Cycode System command implementations
    if args.command == 'cy-info':
        res = system_service.get_root_info()
        if res: print(json.dumps(res, indent=2)); return 0
        return 1
    if args.command == 'cy-health':
        res = system_service.get_health()
        if res: print(json.dumps(res, indent=2)); return 0
        return 1
    if args.command == 'cy-models':
        res = system_service.get_models()
        if res: print(json.dumps(res, indent=2)); return 0
        return 1
    if args.command == 'cy-model-details':
        res = system_service.get_model_details(args.id)
        if res: print(json.dumps(res, indent=2)); return 0
        return 1
    if args.command == 'cy-loadtest-run':
        res = system_service.run_loadtest()
        if res: print(json.dumps(res, indent=2)); return 0
        return 1
    if args.command == 'cy-loadtest-status':
        res = system_service.get_loadtest_status()
        if res: print(json.dumps(res, indent=2)); return 0
        return 1

    # Cycode Inference (Chat) command implementations
    if args.command == 'cy-chat':
        messages = json.loads(args.messages) if args.messages else None
        response = inference_service.post_chat(
            prompt=args.prompt,
            target=args.target,
            max_new_tokens=args.max_tokens,
            session_id=args.session_id,
            messages=messages,
            use_memory=args.use_memory
        )
        if response: print(json.dumps(response, indent=2)); return 0
        return 1

    if args.command == 'cy-chat-stream':
        messages = json.loads(args.messages) if args.messages else None
        for chunk in inference_service.post_chat_stream(
            prompt=args.prompt,
            target=args.target,
            max_new_tokens=args.max_tokens,
            session_id=args.session_id,
            messages=messages,
            use_memory=args.use_memory
        ):
            print(chunk, end='', flush=True)
        print(); return 0

    if args.command == 'cy-chat-history':
        response = inference_service.get_chat_history()
        if response: print(json.dumps(response, indent=2)); return 0
        return 1

    if args.command == 'cy-chat-history-item':
        response = inference_service.get_chat_history_item(args.id)
        if response: print(json.dumps(response, indent=2)); return 0
        return 1

    # Cycode Session command implementations
    if args.command == 'cy-session-create':
        res = inference_service.create_session()
        if res: print(json.dumps(res, indent=2)); return 0
        return 1
    if args.command == 'cy-session-list':
        res = inference_service.get_sessions()
        if res: print(json.dumps(res, indent=2)); return 0
        return 1
    if args.command == 'cy-session-details':
        res = inference_service.get_session_details(args.id)
        if res: print(json.dumps(res, indent=2)); return 0
        return 1
    if args.command == 'cy-session-add-message':
        res = inference_service.add_session_message(args.id, args.role, args.content)
        if res: print(json.dumps(res, indent=2)); return 0
        return 1

    # CyVision command implementations
    if args.command == 'cy-img-generate':
        res = inference_service.generate_image(args.prompt, args.quality)
        if res: print(json.dumps(res, indent=2)); return 0
        return 1
    if args.command == 'cy-img-edit':
        res = inference_service.edit_image(args.image_path, args.prompt)
        if res: print(json.dumps(res, indent=2)); return 0
        return 1
    if args.command == 'cy-img-analyze':
        res = inference_service.analyze_image(args.image_path)
        if res: print(json.dumps(res, indent=2)); return 0
        return 1

    # Code command implementations
    if args.command == 'cy-code-execute':
        res = inference_service.execute_code(args.code, args.lang, args.timeout)
        if res: print(json.dumps(res, indent=2)); return 0
        return 1
    if args.command == 'cy-code-analyze':
        res = inference_service.analyze_code(args.code)
        if res: print(json.dumps(res, indent=2)); return 0
        return 1
    if args.command == 'cy-code-refactor':
        res = inference_service.refactor_code(args.code)
        if res: print(json.dumps(res, indent=2)); return 0
        return 1

    # Admin command implementations
    if args.command == 'cy-auth-status':
        res = admin_service.get_auth_status()
        if res: print(json.dumps(res, indent=2)); return 0
        return 1
    if args.command == 'cy-key-create':
        res = admin_service.create_api_key(args.label)
        if res: print(json.dumps(res, indent=2)); return 0
        return 1
    if args.command == 'cy-key-list':
        res = admin_service.list_api_keys()
        if res: print(json.dumps(res, indent=2)); return 0
        return 1
    if args.command == 'cy-key-delete':
        res = admin_service.delete_api_key(args.label)
        if res: print(json.dumps(res, indent=2)); return 0
        return 1
    if args.command == 'cy-queue-list':
        res = admin_service.list_jobs()
        if res: print(json.dumps(res, indent=2)); return 0
        return 1
    if args.command == 'cy-queue-status':
        res = admin_service.get_job_status(args.id)
        if res: print(json.dumps(res, indent=2)); return 0
        return 1
    if args.command == 'cy-logs':
        res = admin_service.get_logs()
        if res: print(json.dumps(res, indent=2)); return 0
        return 1
    if args.command == 'cy-metrics-usage':
        res = admin_service.get_usage_metrics()
        if res: print(json.dumps(res, indent=2)); return 0
        return 1

    parser.error(f'unknown command: {args.command}')
    return 2


if __name__ == '__main__':
    raise SystemExit(main())
