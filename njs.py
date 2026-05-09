# ©️ Codrago, 2024-2030
# This file is a part of Heroku Userbot
# 🌐 https://github.com/coddrago/Heroku
# You can redistribute it and/or modify it under the terms of the GNU AGPLv3
# 🔑 https://www.gnu.org/licenses/agpl-3.0.html

import asyncio
import shlex
import typing

from .. import loader, utils
from .terminal import InlineMessageEditor

NODEJS_PAGE_SIZE = 7
NODEJS_RISK_ICONS = {
    "success": "✅",
    "primary": "🔷",
    "danger": "🚨",
}


def _nodejs_q(value: str) -> str:
    return shlex.quote(value)


def _nodejs_spec(
    key: str,
    command: str,
    label: str,
    style: str = "success",
) -> dict:
    return {
        "key": key,
        "command": command,
        "label": label,
        "style": style,
    }


def _nodejs_node_expr(key: str, label: str, expression: str) -> dict:
    return _nodejs_spec(key, f"node -p {_nodejs_q(expression)}", label)


def _nodejs_node_script(key: str, label: str, script: str) -> dict:
    return _nodejs_spec(key, f"node -e {_nodejs_q(script)}", label)


def _nodejs_limit(specs: typing.Iterable[dict]) -> tuple:
    return tuple(list(specs)[:100])


def _nodejs_runtime_specs() -> tuple:
    expressions = [
        ("node version", "process.version"),
        ("npm exec path", "process.env.npm_execpath || ''"),
        ("npm node exec", "process.env.npm_node_execpath || ''"),
        ("platform", "process.platform"),
        ("arch", "process.arch"),
        ("platform + arch", "process.platform + ' ' + process.arch"),
        ("cwd", "process.cwd()"),
        ("pid", "process.pid"),
        ("ppid", "process.ppid"),
        ("uptime", "process.uptime()"),
        ("exec path", "process.execPath"),
        ("argv0", "process.argv0"),
        ("argv", "process.argv.join('\\n')"),
        ("exec argv", "process.execArgv.join('\\n')"),
        ("release", "JSON.stringify(process.release, null, 2)"),
        ("versions", "JSON.stringify(process.versions, null, 2)"),
        ("v8 version", "process.versions.v8"),
        ("uv version", "process.versions.uv"),
        ("openssl version", "process.versions.openssl"),
        ("modules abi", "process.versions.modules"),
        ("napi version", "process.versions.napi || ''"),
        ("icu version", "process.versions.icu || ''"),
        ("unicode version", "process.versions.unicode || ''"),
        ("tz version", "process.versions.tz || ''"),
        ("heap usage", "JSON.stringify(process.memoryUsage(), null, 2)"),
        ("rss", "process.memoryUsage().rss"),
        ("heap total", "process.memoryUsage().heapTotal"),
        ("heap used", "process.memoryUsage().heapUsed"),
        ("external memory", "process.memoryUsage().external"),
        ("array buffers", "process.memoryUsage().arrayBuffers"),
        ("resource usage", "JSON.stringify(process.resourceUsage(), null, 2)"),
        ("cpu usage", "JSON.stringify(process.cpuUsage(), null, 2)"),
        ("features", "JSON.stringify(process.features, null, 2)"),
        ("report compact", "JSON.stringify(process.report.getReport().header, null, 2)"),
        ("global paths", "require('module').globalPaths.join('\\n')"),
        ("builtin modules", "require('module').builtinModules.join('\\n')"),
        ("require paths", "require.resolve.paths('npm')?.join('\\n') || ''"),
        ("path delimiter", "require('path').delimiter"),
        ("path sep", "require('path').sep"),
        ("tmpdir", "require('os').tmpdir()"),
        ("homedir", "require('os').homedir()"),
        ("hostname", "require('os').hostname()"),
        ("os type", "require('os').type()"),
        ("os release", "require('os').release()"),
        ("os version", "require('os').version?.() || ''"),
        ("os platform", "require('os').platform()"),
        ("os arch", "require('os').arch()"),
        ("endianness", "require('os').endianness()"),
        ("cpus count", "require('os').cpus().length"),
        ("cpus model", "require('os').cpus()[0]?.model || ''"),
        ("load average", "require('os').loadavg().join(' ')"),
        ("total memory", "require('os').totalmem()"),
        ("free memory", "require('os').freemem()"),
        ("network names", "Object.keys(require('os').networkInterfaces()).join('\\n')"),
        ("env keys", "Object.keys(process.env).sort().join('\\n')"),
        ("node env", "process.env.NODE_ENV || ''"),
        ("path env", "process.env.PATH || ''"),
        ("shell env", "process.env.SHELL || ''"),
        ("home env", "process.env.HOME || ''"),
        ("user env", "process.env.USER || process.env.USERNAME || ''"),
        ("lang env", "process.env.LANG || ''"),
        ("npm lifecycle event", "process.env.npm_lifecycle_event || ''"),
        ("npm package name", "process.env.npm_package_name || ''"),
        ("npm package version", "process.env.npm_package_version || ''"),
        ("npm config prefix", "process.env.npm_config_prefix || ''"),
        ("npm config cache", "process.env.npm_config_cache || ''"),
        ("npm config registry", "process.env.npm_config_registry || ''"),
        ("yarn version env", "process.env.npm_config_user_agent || ''"),
        ("is tty stdout", "Boolean(process.stdout.isTTY)"),
        ("stdout columns", "process.stdout.columns || ''"),
        ("stdout rows", "process.stdout.rows || ''"),
        ("hrtime", "process.hrtime.bigint().toString()"),
        ("date iso", "new Date().toISOString()"),
        ("timezone", "Intl.DateTimeFormat().resolvedOptions().timeZone"),
        ("locale", "Intl.DateTimeFormat().resolvedOptions().locale"),
        ("random uuid", "crypto.randomUUID()"),
        ("webcrypto", "Boolean(globalThis.crypto?.subtle)"),
        ("fetch exists", "typeof fetch"),
        ("structured clone", "typeof structuredClone"),
        ("text encoder", "typeof TextEncoder"),
        ("url parser", "new URL('https://example.com/a?b=c').hostname"),
        ("base64 test", "Buffer.from('node').toString('base64')"),
        ("buffer constants", "JSON.stringify(require('buffer').constants, null, 2)"),
        ("fs constants", "Object.keys(require('fs').constants).slice(0, 80).join('\\n')"),
        ("signals", "Object.keys(require('os').constants.signals).join('\\n')"),
        ("errors", "Object.keys(require('os').constants.errno).join('\\n')"),
        ("module cache size", "Object.keys(require.cache).length"),
        ("main module", "require.main?.filename || ''"),
        ("stdin readable", "process.stdin.readable"),
        ("stdout writable", "process.stdout.writable"),
        ("stderr writable", "process.stderr.writable"),
        ("umask", "process.umask().toString(8)"),
        ("allowed flags", "process.allowedNodeEnvironmentFlags.size"),
        ("diagnostic dir", "process.report.directory"),
        ("diagnostic filename", "process.report.filename"),
        ("diagnostic signal", "process.report.signal"),
        ("debug port", "process.debugPort"),
        ("title", "process.title"),
        ("exit code", "process.exitCode ?? ''"),
        ("config variables", "JSON.stringify(process.config.variables, null, 2)"),
    ]
    specs = [
        _nodejs_spec("node_v", "node -v", "node -v"),
        _nodejs_spec("npm_v", "npm -v", "npm -v"),
        _nodejs_spec("npx_v", "npx -v", "npx -v"),
        _nodejs_spec("corepack_v", "corepack -v", "corepack -v"),
        _nodejs_spec("yarn_v", "yarn -v", "yarn -v"),
        _nodejs_spec("pnpm_v", "pnpm -v", "pnpm -v"),
        _nodejs_spec("bun_v", "bun -v", "bun -v"),
        _nodejs_spec("node_paths", "which node; which npm; which npx", "node paths"),
        _nodejs_spec(
            "node_all_paths",
            "for bin in node npm npx corepack yarn pnpm bun; do "
            "printf '%s: ' \"$bin\"; command -v \"$bin\" || true; done",
            "all binary paths",
        ),
    ]
    specs += [
        _nodejs_node_expr(f"runtime_{index:03}", label, expression)
        for index, (label, expression) in enumerate(expressions, 1)
    ]
    return _nodejs_limit(specs)


def _nodejs_npm_specs() -> tuple:
    specs = [
        _nodejs_spec("pkg_cat", "test -f package.json && cat package.json || echo 'package.json not found'", "cat package.json"),
        _nodejs_spec("pkg_scripts", "npm run", "npm scripts"),
        _nodejs_spec("pkg_list", "npm list --depth=0", "local deps"),
        _nodejs_spec("pkg_list_all", "npm list", "deps tree"),
        _nodejs_spec("pkg_list_global", "npm list -g --depth=0", "global deps"),
        _nodejs_spec("pkg_outdated", "npm outdated || true", "outdated"),
        _nodejs_spec("pkg_audit", "npm audit --audit-level=low || true", "audit"),
        _nodejs_spec("pkg_fund", "npm fund || true", "fund"),
        _nodejs_spec("pkg_config", "npm config list", "npm config"),
        _nodejs_spec("pkg_registry", "npm config get registry", "registry"),
        _nodejs_spec("pkg_cache_verify", "npm cache verify", "cache verify"),
        _nodejs_spec("pkg_doctor", "npm doctor || true", "npm doctor"),
        _nodejs_spec("pkg_ping", "npm ping || true", "npm ping"),
        _nodejs_spec("pkg_whoami", "npm whoami || true", "npm whoami"),
    ]
    pkg_exprs = [
        ("pkg name", "const p=require('./package.json'); console.log(p.name || '')"),
        ("pkg version", "const p=require('./package.json'); console.log(p.version || '')"),
        ("pkg type", "const p=require('./package.json'); console.log(p.type || '')"),
        ("pkg private", "const p=require('./package.json'); console.log(p.private ?? '')"),
        ("pkg license", "const p=require('./package.json'); console.log(p.license || '')"),
        ("pkg author", "const p=require('./package.json'); console.log(typeof p.author === 'string' ? p.author : JSON.stringify(p.author || ''))"),
        ("pkg main", "const p=require('./package.json'); console.log(p.main || '')"),
        ("pkg module", "const p=require('./package.json'); console.log(p.module || '')"),
        ("pkg bin", "const p=require('./package.json'); console.log(JSON.stringify(p.bin || {}, null, 2))"),
        ("pkg engines", "const p=require('./package.json'); console.log(JSON.stringify(p.engines || {}, null, 2))"),
        ("pkg files", "const p=require('./package.json'); console.log((p.files || []).join('\\n'))"),
        ("pkg keywords", "const p=require('./package.json'); console.log((p.keywords || []).join('\\n'))"),
        ("pkg deps", "const p=require('./package.json'); console.log(Object.keys(p.dependencies || {}).join('\\n'))"),
        ("pkg dev deps", "const p=require('./package.json'); console.log(Object.keys(p.devDependencies || {}).join('\\n'))"),
        ("pkg peer deps", "const p=require('./package.json'); console.log(Object.keys(p.peerDependencies || {}).join('\\n'))"),
        ("pkg optional deps", "const p=require('./package.json'); console.log(Object.keys(p.optionalDependencies || {}).join('\\n'))"),
        ("pkg scripts only", "const p=require('./package.json'); console.log(Object.keys(p.scripts || {}).join('\\n'))"),
        ("pkg repo", "const p=require('./package.json'); console.log(JSON.stringify(p.repository || '', null, 2))"),
        ("pkg bugs", "const p=require('./package.json'); console.log(JSON.stringify(p.bugs || '', null, 2))"),
        ("pkg homepage", "const p=require('./package.json'); console.log(p.homepage || '')"),
    ]
    specs += [
        _nodejs_node_script(f"pkg_read_{index:03}", label, script)
        for index, (label, script) in enumerate(pkg_exprs, 1)
    ]
    specs.extend(
        [
            _nodejs_spec("npm_init", "npm init -y", "npm init -y", "primary"),
            _nodejs_spec("npm_install", "npm install", "npm install", "primary"),
            _nodejs_spec("npm_ci", "npm ci", "npm ci", "primary"),
            _nodejs_spec("npm_update", "npm update", "npm update", "primary"),
            _nodejs_spec("npm_dedupe", "npm dedupe", "npm dedupe", "primary"),
            _nodejs_spec("npm_prune", "npm prune", "npm prune", "primary"),
            _nodejs_spec("npm_audit_fix", "npm audit fix", "audit fix", "primary"),
            _nodejs_spec("npm_cache_clean", "npm cache clean --force", "cache clean", "danger"),
            _nodejs_spec("npm_audit_force", "npm audit fix --force", "audit fix --force", "danger"),
            _nodejs_spec("npm_publish", "npm publish", "npm publish", "danger"),
            _nodejs_spec("npm_unpublish_force", "npm unpublish --force", "npm unpublish --force", "danger"),
        ]
    )
    packages = [
        "typescript",
        "eslint",
        "prettier",
        "vite",
        "webpack",
        "rollup",
        "jest",
        "vitest",
        "tsx",
        "nodemon",
        "express",
        "axios",
        "lodash",
        "react",
        "next",
        "vue",
        "svelte",
        "commander",
        "zod",
        "dotenv",
    ]
    for pkg in packages:
        safe_pkg = _nodejs_q(pkg)
        key = pkg.replace("@", "").replace("/", "_").replace("-", "_")
        specs.extend(
            [
                _nodejs_spec(f"npm_view_{key}", f"npm view {safe_pkg} version", f"view {pkg}"),
                _nodejs_spec(f"npm_info_{key}", f"npm info {safe_pkg}", f"info {pkg}"),
                _nodejs_spec(f"npm_install_{key}", f"npm install {safe_pkg}", f"install {pkg}", "primary"),
            ]
        )
    return _nodejs_limit(specs)


def _nodejs_script_specs() -> tuple:
    script_names = [
        "start",
        "dev",
        "serve",
        "preview",
        "build",
        "build:dev",
        "build:prod",
        "watch",
        "test",
        "test:unit",
        "test:e2e",
        "test:watch",
        "test:ci",
        "coverage",
        "lint",
        "lint:fix",
        "format",
        "format:check",
        "typecheck",
        "check",
        "validate",
        "prepare",
        "prepublishOnly",
        "release",
        "clean",
        "reset",
        "seed",
        "migrate",
        "migrate:up",
        "migrate:down",
        "db:push",
        "db:pull",
        "db:reset",
        "db:seed",
        "generate",
        "codegen",
        "storybook",
        "build-storybook",
        "docs",
        "docs:build",
        "analyze",
        "profile",
        "bench",
        "benchmark",
        "postinstall",
        "preinstall",
        "install:all",
        "bootstrap",
        "deploy",
        "deploy:prod",
        "deploy:staging",
        "docker:build",
        "docker:run",
        "heroku-postbuild",
        "worker",
        "queue",
        "cron",
        "sync",
        "import",
        "export",
        "compress",
        "bundle",
        "transpile",
        "compile",
        "copy",
        "assets",
        "assets:build",
        "i18n",
        "locales",
        "mock",
        "mock:server",
        "api",
        "api:dev",
        "server",
        "client",
        "web",
        "mobile",
        "electron",
        "desktop",
        "lambda",
        "functions",
        "schema",
        "graphql",
        "proto",
        "swagger",
        "openapi",
        "devtools",
        "inspect",
        "debug",
        "trace",
        "smoke",
        "health",
        "audit",
        "deps",
        "upgrade",
        "snapshot",
        "snapshot:update",
        "eject",
        "remove",
        "destroy",
        "purge",
    ]
    specs = [
        _nodejs_spec("scripts_list", "npm run", "list scripts"),
        _nodejs_spec("scripts_names", "node -e \"const p=require('./package.json'); console.log(Object.keys(p.scripts||{}).join('\\n') || 'no scripts')\"", "script names"),
    ]
    danger_words = {"release", "deploy", "deploy:prod", "db:reset", "migrate:down", "eject", "remove", "destroy", "purge"}
    primary_words = {"build", "start", "dev", "serve", "watch", "lint:fix", "format", "migrate", "db:push", "seed", "generate", "codegen", "bootstrap", "upgrade"}
    for name in script_names:
        style = "danger" if name in danger_words else "primary" if name in primary_words or ":" in name else "success"
        key = name.replace(":", "_").replace("-", "_")
        specs.append(_nodejs_spec(f"script_{key}", f"npm run {_nodejs_q(name)}", f"run {name}", style))
    return _nodejs_limit(specs)


def _nodejs_pm_specs() -> tuple:
    manager_commands = {
        "yarn": [
            ("version", "yarn -v", "success"),
            ("config", "yarn config list", "success"),
            ("cache dir", "yarn cache dir", "success"),
            ("list", "yarn list --depth=0", "success"),
            ("outdated", "yarn outdated || true", "success"),
            ("why react", "yarn why react || true", "success"),
            ("audit", "yarn audit || true", "success"),
            ("install", "yarn install", "primary"),
            ("add axios", "yarn add axios", "primary"),
            ("add typescript dev", "yarn add -D typescript", "primary"),
            ("remove axios", "yarn remove axios", "primary"),
            ("upgrade", "yarn upgrade", "primary"),
            ("dedupe", "yarn dedupe || true", "primary"),
            ("run build", "yarn build", "primary"),
            ("run test", "yarn test", "primary"),
            ("run lint", "yarn lint", "primary"),
            ("run dev", "yarn dev", "primary"),
            ("set version stable", "yarn set version stable", "danger"),
            ("cache clean", "yarn cache clean", "danger"),
            ("publish", "yarn npm publish", "danger"),
            ("up latest", "yarn up '*'", "danger"),
            ("dlx create vite", "yarn dlx create-vite .", "danger"),
            ("plugin import workspace", "yarn plugin import workspace-tools", "danger"),
            ("constraints", "yarn constraints || true", "success"),
            ("workspaces list", "yarn workspaces list || true", "success"),
        ],
        "pnpm": [
            ("version", "pnpm -v", "success"),
            ("config", "pnpm config list", "success"),
            ("store path", "pnpm store path", "success"),
            ("list", "pnpm list --depth=0", "success"),
            ("outdated", "pnpm outdated || true", "success"),
            ("why react", "pnpm why react || true", "success"),
            ("audit", "pnpm audit || true", "success"),
            ("install", "pnpm install", "primary"),
            ("add axios", "pnpm add axios", "primary"),
            ("add typescript dev", "pnpm add -D typescript", "primary"),
            ("remove axios", "pnpm remove axios", "primary"),
            ("update", "pnpm update", "primary"),
            ("dedupe", "pnpm dedupe", "primary"),
            ("run build", "pnpm run build", "primary"),
            ("run test", "pnpm test", "primary"),
            ("run lint", "pnpm run lint", "primary"),
            ("run dev", "pnpm run dev", "primary"),
            ("store prune", "pnpm store prune", "danger"),
            ("cache delete", "pnpm cache delete --force", "danger"),
            ("publish", "pnpm publish", "danger"),
            ("update latest", "pnpm update --latest", "danger"),
            ("dlx create vite", "pnpm dlx create-vite .", "danger"),
            ("deploy", "pnpm deploy", "danger"),
            ("licenses", "pnpm licenses list || true", "success"),
            ("workspace list", "pnpm -r list --depth=0 || true", "success"),
        ],
        "bun": [
            ("version", "bun -v", "success"),
            ("revision", "bun --revision", "success"),
            ("pm version", "bun pm -v", "success"),
            ("pm bin", "bun pm bin", "success"),
            ("pm ls", "bun pm ls || true", "success"),
            ("x envinfo", "bunx envinfo || true", "success"),
            ("install dry", "bun install --dry-run", "success"),
            ("install", "bun install", "primary"),
            ("add axios", "bun add axios", "primary"),
            ("add typescript dev", "bun add -d typescript", "primary"),
            ("remove axios", "bun remove axios", "primary"),
            ("update", "bun update", "primary"),
            ("run build", "bun run build", "primary"),
            ("run test", "bun test", "primary"),
            ("run lint", "bun run lint", "primary"),
            ("run dev", "bun run dev", "primary"),
            ("create vite", "bun create vite .", "danger"),
            ("pm cache rm", "bun pm cache rm", "danger"),
            ("upgrade", "bun upgrade", "danger"),
            ("publish", "bun publish", "danger"),
            ("run clean", "bun run clean", "danger"),
            ("run deploy", "bun run deploy", "danger"),
            ("run db reset", "bun run db:reset", "danger"),
            ("build src", "bun build src/index.ts --outdir dist", "primary"),
            ("inspect", "bun --inspect index.js", "primary"),
        ],
        "corepack": [
            ("version", "corepack -v", "success"),
            ("help", "corepack --help", "success"),
            ("yarn latest", "corepack yarn -v", "success"),
            ("pnpm latest", "corepack pnpm -v", "success"),
            ("npm version", "corepack npm -v", "success"),
            ("prepare yarn", "corepack prepare yarn@stable --dry-run || true", "success"),
            ("prepare pnpm", "corepack prepare pnpm@latest --dry-run || true", "success"),
            ("enable", "corepack enable", "primary"),
            ("disable", "corepack disable", "primary"),
            ("install global", "corepack install -g yarn@stable", "danger"),
            ("prepare yarn activate", "corepack prepare yarn@stable --activate", "danger"),
            ("prepare pnpm activate", "corepack prepare pnpm@latest --activate", "danger"),
            ("cache clean", "corepack cache clean", "danger"),
            ("use yarn", "corepack use yarn@stable", "danger"),
            ("use pnpm", "corepack use pnpm@latest", "danger"),
            ("pack yarn", "corepack pack yarn@stable", "primary"),
            ("pack pnpm", "corepack pack pnpm@latest", "primary"),
            ("hydrate", "corepack hydrate", "primary"),
            ("install", "corepack install", "primary"),
            ("up", "corepack up", "danger"),
            ("yarn install", "corepack yarn install", "primary"),
            ("pnpm install", "corepack pnpm install", "primary"),
            ("yarn dlx", "corepack yarn dlx envinfo", "primary"),
            ("pnpm dlx", "corepack pnpm dlx envinfo", "primary"),
            ("npm exec", "corepack npm exec envinfo", "primary"),
        ],
    }
    specs = []
    for manager, commands in manager_commands.items():
        for index, (label, command, style) in enumerate(commands, 1):
            key = label.replace(" ", "_").replace(":", "_").replace("-", "_")
            specs.append(_nodejs_spec(f"{manager}_{index:02}_{key}", command, f"{manager} {label}", style))
    return _nodejs_limit(specs)


def _nodejs_tool_specs() -> tuple:
    specs = [
        _nodejs_spec("find_packages", "find . -maxdepth 3 -name package.json -not -path './node_modules/*'", "find package.json"),
        _nodejs_spec("find_locks", "find . -maxdepth 3 \\( -name package-lock.json -o -name yarn.lock -o -name pnpm-lock.yaml -o -name bun.lockb \\) -not -path './node_modules/*'", "find locks"),
        _nodejs_spec("node_modules_size", "du -sh node_modules 2>/dev/null || echo 'node_modules not found'", "node_modules size"),
        _nodejs_spec("source_files", "find . -maxdepth 2 -type f \\( -name '*.js' -o -name '*.mjs' -o -name '*.cjs' -o -name '*.ts' -o -name '*.tsx' -o -name '*.jsx' \\) -not -path './node_modules/*' | sort", "source files"),
    ]
    tools = [
        ("tsc check", "npx tsc --noEmit", "primary"),
        ("eslint", "npx eslint .", "primary"),
        ("eslint fix", "npx eslint . --fix", "danger"),
        ("prettier check", "npx prettier . --check", "success"),
        ("prettier write", "npx prettier . --write", "danger"),
        ("vitest", "npx vitest run", "primary"),
        ("jest", "npx jest", "primary"),
        ("mocha", "npx mocha", "primary"),
        ("ava", "npx ava", "primary"),
        ("c8", "npx c8 npm test", "primary"),
        ("nyc", "npx nyc npm test", "primary"),
        ("vite build", "npx vite build", "primary"),
        ("vite dev", "npx vite --host 0.0.0.0", "primary"),
        ("webpack", "npx webpack", "primary"),
        ("rollup", "npx rollup -c", "primary"),
        ("parcel build", "npx parcel build index.html", "primary"),
        ("next build", "npx next build", "primary"),
        ("next dev", "npx next dev", "primary"),
        ("nuxt build", "npx nuxi build", "primary"),
        ("svelte check", "npx svelte-check", "primary"),
        ("astro check", "npx astro check", "primary"),
        ("astro build", "npx astro build", "primary"),
        ("storybook", "npx storybook dev -p 6006", "primary"),
        ("storybook build", "npx storybook build", "primary"),
        ("envinfo", "npx envinfo", "success"),
        ("npm-check-updates", "npx npm-check-updates", "success"),
        ("ncu upgrade", "npx npm-check-updates -u", "danger"),
        ("depcheck", "npx depcheck", "success"),
        ("license checker", "npx license-checker --summary", "success"),
        ("madge circular", "npx madge --circular .", "success"),
        ("knip", "npx knip", "success"),
        ("ts-prune", "npx ts-prune", "success"),
        ("jscpd", "npx jscpd .", "success"),
        ("npm pack dry", "npm pack --dry-run", "success"),
        ("npm pack", "npm pack", "primary"),
        ("clean node_modules", "rm -rf node_modules", "danger"),
        ("clean npm lock", "rm -f package-lock.json", "danger"),
        ("clean yarn lock", "rm -f yarn.lock", "danger"),
        ("clean pnpm lock", "rm -f pnpm-lock.yaml", "danger"),
        ("clean bun lock", "rm -f bun.lockb", "danger"),
        ("clean dist", "rm -rf dist build .next .nuxt .svelte-kit coverage", "danger"),
        ("clean caches", "rm -rf .cache .parcel-cache .turbo .vite node_modules/.cache", "danger"),
    ]
    specs += [
        _nodejs_spec(
            f"tool_{index:03}_{label.replace(' ', '_').replace('-', '_')}",
            command,
            label,
            style,
        )
        for index, (label, command, style) in enumerate(tools, 1)
    ]
    extra_tools = [
        "create-vite",
        "create-next-app",
        "create-react-app",
        "create-svelte",
        "create-astro",
        "create-nuxt",
        "create-expo-app",
        "create-remix",
        "create-electron-app",
        "degit",
        "serve",
        "http-server",
        "localtunnel",
        "nodemon",
        "tsx",
        "ts-node",
        "esbuild",
        "swc",
        "babel",
        "browserslist",
        "update-browserslist-db",
        "prisma",
        "drizzle-kit",
        "typeorm",
        "sequelize-cli",
        "openapi-typescript",
        "graphql-codegen",
        "swagger-cli",
        "rimraf",
        "shx",
        "cross-env",
        "concurrently",
        "npm-run-all",
        "turbo",
        "nx",
        "lerna",
        "changeset",
        "semantic-release",
        "release-it",
        "husky",
        "lint-staged",
        "commitlint",
        "playwright",
        "cypress",
        "puppeteer",
        "sharp-cli",
        "svgo",
        "imagemin",
        "html-minifier-terser",
        "terser",
        "sass",
        "less",
        "postcss",
        "tailwindcss",
        "daisyui",
    ]
    for index, tool in enumerate(extra_tools, 1):
        style = "danger" if tool.startswith("create-") or tool in {"rimraf", "changeset", "semantic-release", "release-it", "prisma", "drizzle-kit"} else "primary"
        specs.append(
            _nodejs_spec(
                f"npx_{index:03}_{tool.replace('-', '_')}",
                f"npx {tool} --help",
                f"npx {tool}",
                style,
            )
        )
    return _nodejs_limit(specs)


NODEJS_CATEGORIES = (
    ("runtime", "Runtime / env", _nodejs_runtime_specs()),
    ("npm", "npm / package.json", _nodejs_npm_specs()),
    ("scripts", "npm scripts", _nodejs_script_specs()),
    ("managers", "yarn / pnpm / bun / corepack", _nodejs_pm_specs()),
    ("tools", "tools / maintenance", _nodejs_tool_specs()),
)

NODEJS_CATEGORY_MAP = {category[0]: category for category in NODEJS_CATEGORIES}
NODEJS_PRESET_MAP = {
    spec["key"]: spec
    for _, _, specs in NODEJS_CATEGORIES
    for spec in specs
}


@loader.tds
class NodeJSMod(loader.Module):
    """Node.js helper commands"""

    strings = {
        "name": "NodeJS",
        "nodejs_menu": (
            "<b>Node.js helper</b>\n\n"
            "Choose a command category or run <code>.nodejs &lt;node/npm/npx "
            "command&gt;</code>.\n\n"
            "✅ success - read-only or safe\n"
            "🔷 primary - can change project state\n"
            "🚨 danger - can break project, cache or publish state"
        ),
        "nodejs_category_page": (
            "<b>Node.js helper</b>\n\n"
            "<b>{}</b>\n"
            "<b>Page {}/{}</b>\n\n"
            "✅ safe  🔷 changes  🚨 dangerous"
        ),
        "nodejs_unknown_preset": "Unknown Node.js preset",
        "nodejs_no_command": "<b>Node.js command is empty</b>",
        "nodejs_no_terminal": "<b>Terminal module is not loaded</b>",
        "nodejs_btn_categories": "« Categories",
        "nodejs_btn_prev": "« Back",
        "nodejs_btn_next": "Next »",
        "nodejs_btn_close": "Close",
        "_cmd_doc_nodejs": (
            "[node/npm/npx command] - Node.js helper. Without args shows preset "
            "inline buttons"
        ),
    }

    strings_ru = {
        "nodejs_menu": (
            "<b>Node.js helper</b>\n\n"
            "Выбери категорию команд или запусти <code>.nodejs &lt;node/npm/npx "
            "команда&gt;</code>.\n\n"
            "✅ success - безопасные команды\n"
            "🔷 primary - могут изменить проект\n"
            "🚨 danger - могут сломать проект, кеш или публикацию"
        ),
        "nodejs_category_page": (
            "<b>Node.js helper</b>\n\n"
            "<b>{}</b>\n"
            "<b>Страница {}/{}</b>\n\n"
            "✅ safe  🔷 changes  🚨 dangerous"
        ),
        "nodejs_unknown_preset": "Неизвестная Node.js команда",
        "nodejs_no_command": "<b>Node.js команда пустая</b>",
        "nodejs_no_terminal": "<b>Модуль Terminal не загружен</b>",
        "nodejs_btn_categories": "« Категории",
        "nodejs_btn_prev": "« Назад",
        "nodejs_btn_next": "Дальше »",
        "nodejs_btn_close": "Закрыть",
        "_cmd_doc_nodejs": (
            "[node/npm/npx команда] - помощник для Node.js. Без аргументов "
            "показывает инлайн-кнопки с готовыми командами"
        ),
    }

    NODEJS_BINARIES = {
        "node",
        "npm",
        "npx",
        "corepack",
        "yarn",
        "pnpm",
        "bun",
    }

    def _terminal_module(self):
        return self.allmodules.lookup("Terminal")

    def _nodejs_menu_text(
        self,
        category_key: typing.Optional[str] = None,
        page: int = 0,
    ) -> str:
        if category_key is None:
            return self.strings("nodejs_menu")

        _, title, specs = NODEJS_CATEGORY_MAP[category_key]
        total_pages = max(1, (len(specs) + NODEJS_PAGE_SIZE - 1) // NODEJS_PAGE_SIZE)
        page = max(0, min(page, total_pages - 1))
        return self.strings("nodejs_category_page").format(
            title,
            page + 1,
            total_pages,
        )

    def _nodejs_categories_markup(self) -> list:
        markup = [
            [
                {
                    "text": f"{title} ({len(specs)})",
                    "callback": self._nodejs_page,
                    "args": (category_key, 0),
                    "style": "primary",
                }
            ]
            for category_key, title, specs in NODEJS_CATEGORIES
        ]
        markup.append([{"text": self.strings("nodejs_btn_close"), "action": "close"}])
        return markup

    def _nodejs_markup(self, category_key: str, page: int = 0) -> list:
        _, _, specs = NODEJS_CATEGORY_MAP[category_key]
        total_pages = max(1, (len(specs) + NODEJS_PAGE_SIZE - 1) // NODEJS_PAGE_SIZE)
        page = max(0, min(page, total_pages - 1))
        start = page * NODEJS_PAGE_SIZE
        current_specs = specs[start : start + NODEJS_PAGE_SIZE]
        markup = []

        for spec in current_specs:
            icon = NODEJS_RISK_ICONS.get(spec["style"], "")
            markup.append(
                [
                    {
                        "text": f"{icon} {spec['label']}",
                        "callback": self._nodejs_run_preset,
                        "args": (spec["key"],),
                        "style": spec["style"],
                    }
                ]
            )

        markup.append(
            [
                {
                    "text": self.strings("nodejs_btn_categories"),
                    "callback": self._nodejs_categories,
                    "style": "primary",
                }
            ]
        )
        nav = []
        if page > 0:
            nav.append(
                {
                    "text": self.strings("nodejs_btn_prev"),
                    "callback": self._nodejs_page,
                    "args": (category_key, page - 1),
                    "style": "primary",
                }
            )

        if page < total_pages - 1:
            nav.append(
                {
                    "text": self.strings("nodejs_btn_next"),
                    "callback": self._nodejs_page,
                    "args": (category_key, page + 1),
                    "style": "primary",
                }
            )

        if nav:
            markup.append(nav)

        markup.append([{"text": self.strings("nodejs_btn_close"), "action": "close"}])
        return markup

    def _nodejs_command_from_args(self, args: str) -> str:
        args = args.strip().replace("\xa0", "\x20")
        if not args:
            return ""

        try:
            first = shlex.split(args, posix=True)[0]
        except ValueError:
            first = args.split(maxsplit=1)[0]

        if first in self.NODEJS_BINARIES:
            return args

        return f"node {args}"

    async def _nodejs_categories(self, call):
        await call.edit(
            self._nodejs_menu_text(),
            reply_markup=self._nodejs_categories_markup(),
        )

    async def _nodejs_page(self, call, category_key: str, page: int = 0):
        if category_key not in NODEJS_CATEGORY_MAP:
            await call.answer(self.strings("nodejs_unknown_preset"), show_alert=True)
            return

        await call.edit(
            self._nodejs_menu_text(category_key, page),
            reply_markup=self._nodejs_markup(category_key, page),
        )

    async def _nodejs_run_preset(self, call, key: str):
        terminal = self._terminal_module()
        if not terminal:
            await call.answer(self.strings("nodejs_no_terminal"), show_alert=True)
            return

        preset = NODEJS_PRESET_MAP.get(key)
        if not preset:
            await call.answer(self.strings("nodejs_unknown_preset"), show_alert=True)
            return

        cmd = preset["command"]
        if terminal._is_dangerous(cmd):
            await call.answer(
                terminal.strings("dangerous_command").format(cmd),
                show_alert=True,
            )
            return

        await call.edit(terminal.strings("exec_running"))

        editor = InlineMessageEditor(
            form=call,
            command=cmd,
            strings=terminal.strings,
            config=terminal.config,
        )

        asyncio.ensure_future(terminal._run_inline(cmd, editor))

    @loader.command(alias="node")
    async def nodejscmd(self, message):
        """[node/npm/npx command] - Node.js helper"""
        terminal = self._terminal_module()
        if not terminal:
            await utils.answer(message, self.strings("nodejs_no_terminal"))
            return

        args = utils.get_args_raw(message)
        reply = await message.get_reply_message()

        if not args and reply and reply.text:
            args = reply.message

        if not args:
            await utils.answer(
                message,
                self._nodejs_menu_text(),
                reply_markup=self._nodejs_categories_markup(),
            )
            return

        cmd = self._nodejs_command_from_args(args)
        if not cmd:
            await utils.answer(message, self.strings("nodejs_no_command"))
            return

        await terminal.run_command(message, cmd)
