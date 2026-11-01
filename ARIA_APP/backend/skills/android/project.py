from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import time
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

PROJECTS_DIR = Path(__file__).resolve().parents[2] / "data" / "android_projects"


# ─── Utilidades ──────────────────────────────────────────────────────────────

def _slug(name: str) -> str:
    return "".join(c if c.isalnum() else "_" for c in name).strip("_") or "app"


def _package_path(package: str) -> str:
    return package.replace(".", "/")


def _proj_dir(project: str) -> Path:
    return PROJECTS_DIR / _slug(project)


def _safe_rel(project: str, rel: str) -> Path:
    base = _proj_dir(project).resolve()
    target = (base / rel).resolve()
    try:
        target.relative_to(base)
    except ValueError:
        raise PermissionError(f"ruta fuera del proyecto: {rel}")
    return target


def _list_files(base: Path) -> List[str]:
    out: List[str] = []
    if not base.exists():
        return out
    for p in sorted(base.rglob("*")):
        if p.is_file():
            out.append(str(p.relative_to(base)))
    return out


def _read_file(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return path.read_bytes().decode("latin-1", errors="replace")


def _meta(project: str) -> Dict[str, Any]:
    p = _proj_dir(project) / ".aria_android_meta.json"
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _save_meta(project: str, meta: Dict[str, Any]) -> None:
    p = _proj_dir(project) / ".aria_android_meta.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")


# ─── Crear proyecto completo ─────────────────────────────────────────────────

def create_project(params: Dict[str, Any]) -> Dict[str, Any]:
    app_name = str(params.get("app_name", "MiApp")).strip()
    package = str(params.get("package", "com.aria.app")).strip()
    activity = str(params.get("activity", "MainActivity")).strip()
    min_sdk = str(params.get("min_sdk", "21")).strip()
    target_sdk = str(params.get("target_sdk", "34")).strip()
    compile_sdk = str(params.get("compile_sdk", "34")).strip()
    language = str(params.get("language", "kotlin")).strip().lower()
    theme = str(params.get("theme", "AppCompat.Light.DarkActionBar")).strip()
    enable_viewbinding = bool(params.get("viewbinding", True))
    enable_databinding = bool(params.get("databinding", False))

    project_dir = _proj_dir(app_name)
    project_dir.mkdir(parents=True, exist_ok=True)

    pkg_rel = _package_path(package)
    ext = "kt" if language == "kotlin" else "java"
    java_dir = project_dir / "app" / "src" / "main" / "java" / pkg_rel
    res_dir = project_dir / "app" / "src" / "main" / "res"
    gradle_dir = project_dir / "gradle" / "wrapper"

    java_dir.mkdir(parents=True, exist_ok=True)
    (res_dir / "values").mkdir(parents=True, exist_ok=True)
    (res_dir / "layout").mkdir(parents=True, exist_ok=True)
    (res_dir / "drawable").mkdir(parents=True, exist_ok=True)
    (res_dir / "mipmap-anydpi-v26").mkdir(parents=True, exist_ok=True)
    gradle_dir.mkdir(parents=True, exist_ok=True)

    files: Dict[str, str] = {}

    files["settings.gradle"] = (
        "pluginManagement {\n"
        "    repositories {\n"
        "        google()\n"
        "        mavenCentral()\n"
        "    }\n"
        "    dependencyResolutionManagement {\n"
        "        repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)\n"
        "        repositories {\n"
        "            google()\n"
        "            mavenCentral()\n"
        "        }\n"
        "    }\n"
        "}\n"
        f"rootProject.name = '{_slug(app_name)}'\n"
        "include ':app'\n"
    )

    files["build.gradle"] = (
        "buildscript {\n"
        "    repositories {\n"
        "        google()\n"
        "        mavenCentral()\n"
        "    }\n"
        "    dependencies {\n"
        "        classpath 'com.android.tools.build:gradle:8.2.0'\n"
        "        classpath 'org.jetbrains.kotlin:kotlin-gradle-plugin:1.9.22'\n"
        "    }\n"
        "}\n"
        "allprojects {\n"
        "    repositories {\n"
        "        google()\n"
        "        mavenCentral()\n"
        "    }\n"
        "}\n"
        "task clean(type: Delete) {\n"
        "    delete rootProject.buildDir\n"
        "}\n"
    )

    android_block = (
        "android {\n"
        f"    namespace '{package}'\n"
        f"    compileSdk {compile_sdk}\n"
        "    defaultConfig {\n"
        f"        applicationId '{package}'\n"
        f"        minSdk {min_sdk}\n"
        f"        targetSdk {target_sdk}\n"
        "        versionCode 1\n"
        "        versionName '1.0'\n"
        "    }\n"
        "    buildTypes {\n"
        "        release {\n"
        "            minifyEnabled false\n"
        "            proguardFiles getDefaultProguardFile('proguard-android-optimize.txt'), 'proguard-rules.pro'\n"
        "        }\n"
        "        debug {\n"
        "            minifyEnabled false\n"
        "        }\n"
        "    }\n"
        "    compileOptions {\n"
        "        sourceCompatibility JavaVersion.VERSION_1_8\n"
        "        targetCompatibility JavaVersion.VERSION_1_8\n"
        "    }\n"
    )
    if language == "kotlin":
        android_block += (
        "    kotlinOptions {\n"
        "        jvmTarget = '1.8'\n"
        "    }\n"
        )
    if enable_viewbinding:
        android_block += "    buildFeatures {\n        viewBinding true\n    }\n"
    if enable_databinding:
        android_block += "    buildFeatures {\n        dataBinding true\n    }\n"
    android_block += "}\n"

    deps = (
        "dependencies {\n"
        "    implementation 'androidx.core:core-ktx:1.12.0'\n"
        "    implementation 'androidx.appcompat:appcompat:1.6.1'\n"
        "    implementation 'com.google.android.material:material:1.11.0'\n"
        "    implementation 'androidx.constraintlayout:constraintlayout:2.1.4'\n"
    )
    if language == "kotlin":
        deps += "    implementation 'org.jetbrains.kotlin:kotlin-stdlib:1.9.22'\n"
    deps += "}\n"

    files["app/build.gradle"] = (
        "plugins {\n"
        "    id 'com.android.application'\n"
    ) + (f"    id 'org.jetbrains.kotlin.android'\n" if language == "kotlin" else "") + (
        "}\n"
        "\n"
        + android_block
        + "\n"
        + deps
    )

    files["gradle/wrapper/gradle-wrapper.properties"] = (
        "distributionBase=GRADLE_USER_HOME\n"
        "distributionPath=wrapper/dists\n"
        "distributionUrl=https\\://services.gradle.org/distributions/gradle-8.2-bin.zip\n"
        "zipStoreBase=GRADLE_USER_HOME\n"
        "zipStorePath=wrapper/dists\n"
    )

    files["app/src/main/AndroidManifest.xml"] = (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<manifest xmlns:android="http://schemas.android.com/apk/res/android"\n'
        f'    package="{package}">\n'
        '\n'
        '    <uses-permission android:name="android.permission.INTERNET" />\n'
        '    <uses-permission android:name="android.permission.ACCESS_NETWORK_STATE" />\n'
        '\n'
        f'    <application\n'
        '        android:allowBackup="true"\n'
        '        android:icon="@mipmap/ic_launcher"\n'
        '        android:roundIcon="@mipmap/ic_launcher_round"\n'
        f'        android:label="@string/app_name"\n'
        f'        android:theme="@style/Theme.{theme}"\n'
        '        android:supportsRtl="true">\n'
        f'        <activity\n'
        f'            android:name=".{activity}"\n'
        '            android:exported="true">\n'
        '            <intent-filter>\n'
        '                <action android:name="android.intent.action.MAIN" />\n'
        '                <category android:name="android.intent.category.LAUNCHER" />\n'
        '            </intent-filter>\n'
        '        </activity>\n'
        '    </application>\n'
        '</manifest>\n'
    )

    files["app/src/main/res/values/strings.xml"] = (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<resources>\n'
        f'    <string name="app_name">{app_name}</string>\n'
        '</resources>\n'
    )

    files["app/src/main/res/values/themes.xml"] = (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<resources>\n'
        f'    <style name="Theme.{theme}" parent="android:Theme.Material.Light">\n'
        '        <!-- Customize your theme here -->\n'
        '    </style>\n'
        '</resources>\n'
    )

    files["app/src/main/res/layout/activity_main.xml"] = (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<androidx.constraintlayout.widget.ConstraintLayout\n'
        '    xmlns:android="http://schemas.android.com/apk/res/android"\n'
        '    xmlns:app="http://schemas.android.com/apk/res-auto"\n'
        '    xmlns:tools="http://schemas.android.com/tools"\n'
        '    android:layout_width="match_parent"\n'
        '    android:layout_height="match_parent"\n'
        f'    tools:context=".{activity}">\n'
        '\n'
        '    <TextView\n'
        '        android:id="@+id/textView"\n'
        '        android:layout_width="wrap_content"\n'
        '        android:layout_height="wrap_content"\n'
        '        android:text="Hola desde ARIA"\n'
        '        android:textSize="24sp"\n'
        '        app:layout_constraintBottom_toBottomOf="parent"\n'
        '        app:layout_constraintEnd_toEndOf="parent"\n'
        '        app:layout_constraintStart_toStartOf="parent"\n'
        '        app:layout_constraintTop_toTopOf="parent" />\n'
        '\n'
        '</androidx.constraintlayout.widget.ConstraintLayout>\n'
    )

    activity_code = (
        f"package {package}\n"
        '\n'
        + ("import android.os.Bundle\n" if language == "kotlin" else "")
        + ("import androidx.appcompat.app.AppCompatActivity\n" if language == "kotlin"
           else "import androidx.appcompat.app.AppCompatActivity;\n"
              "import android.os.Bundle;\n")
        + "\n"
    )
    if language == "kotlin":
        activity_code += (
            f"class {activity} : AppCompatActivity() {{\n"
            '    override fun onCreate(savedInstanceState: Bundle?) {\n'
            '        super.onCreate(savedInstanceState)\n'
            f'        setContentView(R.layout.activity_main)\n'
            '    }\n'
            '}\n'
        )
    else:
        activity_code += (
            f"public class {activity} extends AppCompatActivity {{\n"
            '    @Override\n'
            '    protected void onCreate(Bundle savedInstanceState) {\n'
            '        super.onCreate(savedInstanceState);\n'
            f'        setContentView(R.layout.activity_main);\n'
            '    }\n'
            '}\n'
        )

    files[f"app/src/main/java/{pkg_rel}/{activity}.{ext}"] = activity_code

    written: List[str] = []
    for rel, content in files.items():
        p = project_dir / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        written.append(str(p))

    meta = {
        "app_name": app_name,
        "package": package,
        "activity": activity,
        "min_sdk": min_sdk,
        "target_sdk": target_sdk,
        "compile_sdk": compile_sdk,
        "language": language,
        "theme": theme,
        "viewbinding": enable_viewbinding,
        "databinding": enable_databinding,
        "created_at": datetime.now().isoformat(),
        "path": str(project_dir),
        "files": _list_files(project_dir),
    }
    _save_meta(app_name, meta)

    return {
        "status": "ok",
        "skill": "android_create_project",
        "project": app_name,
        "package": package,
        "activity": activity,
        "language": language,
        "path": str(project_dir),
        "files_created": len(written),
        "structure": _list_files(project_dir),
        "message": f"Proyecto Android '{app_name}' creado completamente en {project_dir}. Abre la carpeta en Android Studio.",
    }


# ─── Agregar componentes ─────────────────────────────────────────────────────

def add_activity(params: Dict[str, Any]) -> Dict[str, Any]:
    project = str(params.get("project", "")).strip()
    name = str(params.get("name", "SecondActivity")).strip()
    layout = str(params.get("layout", "activity_second")).strip()
    if not project:
        return {"error": "project requerido"}
    base = _proj_dir(project)
    if not base.exists():
        return {"error": f"proyecto no encontrado: {project}"}
    meta = _meta(project)
    package = meta.get("package", "com.aria.app")
    language = meta.get("language", "kotlin")
    ext = "kt" if language == "kotlin" else "java"
    pkg_rel = _package_path(package)
    java_dir = base / "app" / "src" / "main" / "java" / pkg_rel
    res_layout = base / "app" / "src" / "main" / "res" / "layout"
    java_dir.mkdir(parents=True, exist_ok=True)
    res_layout.mkdir(parents=True, exist_ok=True)

    java_file = java_dir / f"{name}.{ext}"
    layout_file = res_layout / f"{layout}.xml"

    if language == "kotlin":
        java_content = (
            f"package {package}\n"
            '\n'
            'import android.os.Bundle\n'
            'import androidx.appcompat.app.AppCompatActivity\n'
            "\n"
            f"class {name} : AppCompatActivity() {{\n"
            '    override fun onCreate(savedInstanceState: Bundle?) {\n'
            '        super.onCreate(savedInstanceState)\n'
            f'        setContentView(R.layout.{layout})\n'
            '    }\n'
            '}\n'
        )
    else:
        java_content = (
            f"package {package};\n"
            '\n'
            'import android.os.Bundle;\n'
            'import androidx.appcompat.app.AppCompatActivity;\n'
            "\n"
            f"public class {name} extends AppCompatActivity {{\n"
            '    @Override\n'
            '    protected void onCreate(Bundle savedInstanceState) {\n'
            '        super.onCreate(savedInstanceState);\n'
            f'        setContentView(R.layout.{layout});\n'
            '    }\n'
            '}\n'
        )
    layout_content = (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<androidx.constraintlayout.widget.ConstraintLayout\n'
        '    xmlns:android="http://schemas.android.com/apk/res/android"\n'
        '    xmlns:app="http://schemas.android.com/apk/res-auto"\n'
        '    xmlns:tools="http://schemas.android.com/tools"\n'
        '    android:layout_width="match_parent"\n'
        '    android:layout_height="match_parent">\n'
        '\n'
        '    <TextView\n'
        '        android:id="@+id/textView"\n'
        '        android:layout_width="wrap_content"\n'
        '        android:layout_height="wrap_content"\n'
        f'        android:text="{name}"\n'
        '        android:textSize="24sp"\n'
        '        app:layout_constraintBottom_toBottomOf="parent"\n'
        '        app:layout_constraintEnd_toEndOf="parent"\n'
        '        app:layout_constraintStart_toStartOf="parent"\n'
        '        app:layout_constraintTop_toTopOf="parent" />\n'
        '\n'
        '</androidx.constraintlayout.widget.ConstraintLayout>\n'
    )

    java_file.write_text(java_content, encoding="utf-8")
    layout_file.write_text(layout_content, encoding="utf-8")

    meta.setdefault("activities", []).append(name)
    meta["files"] = _list_files(base)
    _save_meta(project, meta)

    return {
        "status": "ok",
        "skill": "android_add_activity",
        "project": project,
        "activity": name,
        "layout": layout,
        "java_file": str(java_file),
        "layout_file": str(layout_file),
    }


def add_fragment(params: Dict[str, Any]) -> Dict[str, Any]:
    project = str(params.get("project", "")).strip()
    name = str(params.get("name", "PlaceholderFragment")).strip()
    if not project:
        return {"error": "project requerido"}
    base = _proj_dir(project)
    if not base.exists():
        return {"error": f"proyecto no encontrado: {project}"}
    meta = _meta(project)
    package = meta.get("package", "com.aria.app")
    language = meta.get("language", "kotlin")
    ext = "kt" if language == "kotlin" else "java"
    pkg_rel = _package_path(package)
    java_dir = base / "app" / "src" / "main" / "java" / pkg_rel
    java_dir.mkdir(parents=True, exist_ok=True)

    java_file = java_dir / f"{name}.{ext}"
    if language == "kotlin":
        content = (
            f"package {package}\n"
            '\n'
            'import android.os.Bundle\n'
            'import android.view.LayoutInflater\n'
            'import android.view.View\n'
            'import android.view.ViewGroup\n'
            'import androidx.fragment.app.Fragment\n'
            "\n"
            f"class {name} : Fragment() {{\n"
            '    override fun onCreateView(\n'
            '        inflater: LayoutInflater,\n'
            '        container: ViewGroup?,\n'
            '        savedInstanceState: Bundle?\n'
            '    ): View? {\n'
            '        return inflater.inflate(R.layout.fragment_placeholder, container, false)\n'
            '    }\n'
            '}\n'
        )
    else:
        content = (
            f"package {package};\n"
            '\n'
            'import android.os.Bundle;\n'
            'import android.view.LayoutInflater;\n'
            'import android.view.View;\n'
            'import android.view.ViewGroup;\n'
            'import androidx.fragment.app.Fragment;\n'
            "\n"
            f"public class {name} extends Fragment {{\n"
            '    @Override\n'
            '    public View onCreateView(LayoutInflater inflater, ViewGroup container,\n'
            '                                 Bundle savedInstanceState) {\n'
            '        return inflater.inflate(R.layout.fragment_placeholder, container, false);\n'
            '    }\n'
            '}\n'
        )
    java_file.write_text(content, encoding="utf-8")
    meta.setdefault("fragments", []).append(name)
    meta["files"] = _list_files(base)
    _save_meta(project, meta)
    return {
        "status": "ok",
        "skill": "android_add_fragment",
        "project": project,
        "fragment": name,
        "file": str(java_file),
    }


def add_viewmodel(params: Dict[str, Any]) -> Dict[str, Any]:
    project = str(params.get("project", "")).strip()
    name = str(params.get("name", "MainViewModel")).strip()
    if not project:
        return {"error": "project requerido"}
    base = _proj_dir(project)
    if not base.exists():
        return {"error": f"proyecto no encontrado: {project}"}
    meta = _meta(project)
    package = meta.get("package", "com.aria.app")
    language = meta.get("language", "kotlin")
    ext = "kt" if language == "kotlin" else "java"
    pkg_rel = _package_path(package)
    java_dir = base / "app" / "src" / "main" / "java" / pkg_rel
    java_dir.mkdir(parents=True, exist_ok=True)

    java_file = java_dir / f"{name}.{ext}"
    if language == "kotlin":
        content = (
            f"package {package}\n"
            '\n'
            'import androidx.lifecycle.ViewModel\n'
            "\n"
            f"class {name} : ViewModel() {{\n"
            '    // Agrega tu estado y lógica de UI aquí\n'
            '}\n'
        )
    else:
        content = (
            f"package {package};\n"
            '\n'
            'import androidx.lifecycle.ViewModel;\n'
            "\n"
            f"public class {name} extends ViewModel {{\n"
            '    // Agrega tu estado y lógica de UI aquí\n'
            '}\n'
        )
    java_file.write_text(content, encoding="utf-8")
    meta.setdefault("viewmodels", []).append(name)
    meta["files"] = _list_files(base)
    _save_meta(project, meta)
    return {
        "status": "ok",
        "skill": "android_add_viewmodel",
        "project": project,
        "viewmodel": name,
        "file": str(java_file),
    }


def add_permission(params: Dict[str, Any]) -> Dict[str, Any]:
    project = str(params.get("project", "")).strip()
    permission = str(params.get("permission", "android.permission.CAMERA")).strip()
    if not project:
        return {"error": "project requerido"}
    base = _proj_dir(project)
    manifest = base / "app" / "src" / "main" / "AndroidManifest.xml"
    if not manifest.exists():
        return {"error": "AndroidManifest.xml no encontrado"}
    content = manifest.read_text(encoding="utf-8")
    if f'android:name="{permission}"' in content:
        return {"status": "ok", "message": f"permiso ya presente: {permission}"}
    insert_before = "</manifest>"
    perm_line = f'    <uses-permission android:name="{permission}" />\n'
    content = content.replace(insert_before, perm_line + insert_before, 1)
    manifest.write_text(content, encoding="utf-8")
    meta = _meta(project)
    meta.setdefault("permissions", []).append(permission)
    _save_meta(project, meta)
    return {
        "status": "ok",
        "skill": "android_add_permission",
        "project": project,
        "permission": permission,
    }


def add_dependency(params: Dict[str, Any]) -> Dict[str, Any]:
    project = str(params.get("project", "")).strip()
    dep = str(params.get("dependency", "")).strip()
    if not project:
        return {"error": "project requerido"}
    if not dep:
        return {"error": "dependency requerido (ej: 'com.google.android.material:material:1.11.0')"}
    base = _proj_dir(project)
    build_gradle = base / "app" / "build.gradle"
    if not build_gradle.exists():
        return {"error": "app/build.gradle no encontrado"}
    content = build_gradle.read_text(encoding="utf-8")
    line = f"    implementation '{dep}'\n"
    if line.strip() in content:
        return {"status": "ok", "message": f"dependencia ya presente: {dep}"}
    marker = "}\n"
    content = content.rstrip()
    if not content.endswith("dependencies {"):
        content = content.replace("\n}", f"\n    {line.strip()}\n}}", 1)
    else:
        content += line
    build_gradle.write_text(content, encoding="utf-8")
    meta = _meta(project)
    meta.setdefault("dependencies", []).append(dep)
    _save_meta(project, meta)
    return {
        "status": "ok",
        "skill": "android_add_dependency",
        "project": project,
        "dependency": dep,
    }


# ─── Información completa del proyecto ───────────────────────────────────────

def project_info(params: Dict[str, Any]) -> Dict[str, Any]:
    project = str(params.get("project", "")).strip()
    if not project:
        return {"error": "project requerido"}
    base = _proj_dir(project)
    if not base.exists():
        return {"error": f"proyecto no encontrado: {project}"}
    meta = _meta(project)
    files = _list_files(base)
    tree: Dict[str, Any] = {}
    for rel in files:
        parts = Path(rel).parts
        node = tree
        for part in parts[:-1]:
            node = node.setdefault(part, {})
        node[parts[-1]] = "file"
    size = sum((base / f).stat().st_size for f in files if (base / f).exists())
    return {
        "status": "ok",
        "skill": "android_project_info",
        "project": project,
        "meta": meta,
        "file_count": len(files),
        "total_size_bytes": size,
        "structure": tree,
        "files": files,
        "path": str(base),
    }


def list_projects() -> Dict[str, Any]:
    PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
    out: List[Dict[str, Any]] = []
    for d in sorted(PROJECTS_DIR.iterdir()):
        if d.is_dir() and (d / ".aria_android_meta.json").exists():
            meta = _meta(d.name)
            out.append({
                "name": d.name,
                "path": str(d),
                "app_name": meta.get("app_name"),
                "package": meta.get("package"),
                "activity": meta.get("activity"),
                "language": meta.get("language"),
                "file_count": meta.get("file_count", 0),
                "created_at": meta.get("created_at"),
            })
    return {"status": "ok", "skill": "android_list_projects", "projects": out, "count": len(out)}


# ─── Leer / escribir / modificar archivos del proyecto ───────────────────────

def read_file(params: Dict[str, Any]) -> Dict[str, Any]:
    project = str(params.get("project", "")).strip()
    rel = str(params.get("path", "")).strip()
    if not project or not rel:
        return {"error": "project y path requeridos"}
    try:
        p = _safe_rel(project, rel)
    except PermissionError as exc:
        return {"error": str(exc)}
    if not p.exists():
        return {"error": f"archivo no encontrado: {rel}"}
    content = _read_file(p)
    return {
        "status": "ok",
        "skill": "android_read_file",
        "project": project,
        "path": rel,
        "content": content[:20000],
        "size": p.stat().st_size,
    }


def write_file(params: Dict[str, Any]) -> Dict[str, Any]:
    project = str(params.get("project", "")).strip()
    rel = str(params.get("path", "")).strip()
    content = params.get("content", "")
    if not project or not rel:
        return {"error": "project y path requeridos"}
    try:
        p = _safe_rel(project, rel)
    except PermissionError as exc:
        return {"error": str(exc)}
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    meta = _meta(project)
    meta["files"] = _list_files(_proj_dir(project))
    _save_meta(project, meta)
    return {
        "status": "ok",
        "skill": "android_write_file",
        "project": project,
        "path": rel,
        "bytes": len(content.encode("utf-8")),
    }


def modify_file(params: Dict[str, Any]) -> Dict[str, Any]:
    project = str(params.get("project", "")).strip()
    rel = str(params.get("path", "")).strip()
    old = params.get("old", "")
    new = params.get("new", "")
    replace_all = bool(params.get("replace_all", False))
    if not project or not rel:
        return {"error": "project y path requeridos"}
    try:
        p = _safe_rel(project, rel)
    except PermissionError as exc:
        return {"error": str(exc)}
    if not p.exists():
        return {"error": f"archivo no encontrado: {rel}"}
    content = p.read_text(encoding="utf-8")
    if old not in content:
        return {"error": f"texto '{old[:60]}' no encontrado en {rel}"}
    count = None if replace_all else 1
    new_content = content.replace(old, new, count)
    p.write_text(new_content, encoding="utf-8")
    meta = _meta(project)
    meta["files"] = _list_files(_proj_dir(project))
    _save_meta(project, meta)
    return {
        "status": "ok",
        "skill": "android_modify_file",
        "project": project,
        "path": rel,
        "replaced": count,
    }


# ─── Gradle / build ──────────────────────────────────────────────────────────

def generate_gradle_wrapper(params: Dict[str, Any]) -> Dict[str, Any]:
    project = str(params.get("project", "")).strip()
    if not project:
        return {"error": "project requerido"}
    base = _proj_dir(project)
    if not base.exists():
        return {"error": f"proyecto no encontrado: {project}"}
    gradlew = base / "gradlew"
    gradlew_bat = base / "gradlew.bat"
    wrapper_dir = base / "gradle" / "wrapper"
    wrapper_dir.mkdir(parents=True, exist_ok=True)

    props = wrapper_dir / "gradle-wrapper.properties"
    if not props.exists():
        props.write_text(
            "distributionBase=GRADLE_USER_HOME\n"
            "distributionPath=wrapper/dists\n"
            "distributionUrl=https\\://services.gradle.org/distributions/gradle-8.2-bin.zip\n"
            "zipStoreBase=GRADLE_USER_HOME\n"
            "zipStorePath=wrapper/dists\n",
            encoding="utf-8",
        )

    # Instrucciones para que el usuario genere gradlew (necesita Gradle instalado)
    return {
        "status": "ok",
        "skill": "android_generate_gradle_wrapper",
        "project": project,
        "gradle_wrapper_present": gradlew.exists() or gradlew_bat.exists(),
        "message": (
            "Para compilar necesitas el wrapper de Gradle (gradlew / gradlew.bat). "
            "Si Gradle está instalado, ejecuta dentro del proyecto: `gradle wrapper` "
            "o `gradle wrapper --gradle-version 8.2`. Luego usa android_build_apk."
        ),
    }


def build_apk(params: Dict[str, Any]) -> Dict[str, Any]:
    project = str(params.get("project", "")).strip()
    variant = str(params.get("variant", "debug")).strip()
    if not project:
        return {"error": "project requerido"}
    base = _proj_dir(project)
    if not base.exists():
        return {"error": f"proyecto no encontrado: {project}"}
    gradlew = base / "gradlew"
    gradlew_bat = base / "gradlew.bat"
    exe = str(gradlew_bat if gradlew_bat.exists() else gradlew)
    if not (gradlew.exists() or gradlew_bat.exists()):
        return {
            "error": "gradlew no encontrado. Ejecuta android_generate_gradle_wrapper y luego genera el wrapper con Gradle instalado.",
        }
    task = f"assemble{variant.capitalize()}"
    try:
        proc = subprocess.run(
            [exe, task],
            cwd=str(base),
            capture_output=True, text=True, timeout=600,
        )
        apk = base / "app" / "build" / "outputs" / "apk" / variant / f"app-{variant}.apk"
        return {
            "status": "ok" if proc.returncode == 0 else "error",
            "skill": "android_build_apk",
            "project": project,
            "variant": variant,
            "task": task,
            "returncode": proc.returncode,
            "stdout": proc.stdout[-4000:],
            "stderr": proc.stderr[-4000:],
            "apk": str(apk) if apk.exists() else None,
        }
    except subprocess.TimeoutExpired:
        return {"error": "timeout compilando APK (600s)"}
    except Exception as exc:
        return {"error": str(exc)}


# ─── Instalar / ejecutar en dispositivo ──────────────────────────────────────

def install_apk(params: Dict[str, Any]) -> Dict[str, Any]:
    project = str(params.get("project", "")).strip()
    variant = str(params.get("variant", "debug")).strip()
    if not project:
        return {"error": "project requerido"}
    base = _proj_dir(project)
    apk = base / "app" / "build" / "outputs" / "apk" / variant / f"app-{variant}.apk"
    if not apk.exists():
        return {"error": f"APK no encontrado: {apk}. Compila primero con android_build_apk."}
    adb = shutil.which("adb")
    if not adb:
        return {"error": "adb no encontrado en PATH. Instala Android SDK Platform-Tools."}
    try:
        proc = subprocess.run(
            [adb, "install", "-r", str(apk)],
            capture_output=True, text=True, timeout=120,
        )
        return {
            "status": "ok" if proc.returncode == 0 else "error",
            "skill": "android_install_apk",
            "project": project,
            "apk": str(apk),
            "returncode": proc.returncode,
            "stdout": proc.stdout[-2000:],
            "stderr": proc.stderr[-2000:],
        }
    except subprocess.TimeoutExpired:
        return {"error": "timeout instalando APK (120s)"}
    except Exception as exc:
        return {"error": str(exc)}


# ─── Dispatcher ──────────────────────────────────────────────────────────────

def run(params: Dict[str, Any]) -> Dict[str, Any]:
    domain = params.get("domain", "project")
    inner = dict(params)
    inner.pop("domain", None)
    action = inner.get("action", "")

    if domain == "project":
        if action == "create":
            return create_project(inner)
        if action == "info":
            return project_info(inner)
        if action == "list":
            return list_projects()
        if action == "read_file":
            return read_file(inner)
        if action == "write_file":
            return write_file(inner)
        if action == "modify_file":
            return modify_file(inner)
        if action == "generate_gradle_wrapper":
            return generate_gradle_wrapper(inner)
        if action == "build_apk":
            return build_apk(inner)
        if action == "install_apk":
            return install_apk(inner)
        return {"error": f"acción de proyecto desconocida: {action}"}
    if domain == "component":
        if action == "add_activity":
            return add_activity(inner)
        if action == "add_fragment":
            return add_fragment(inner)
        if action == "add_viewmodel":
            return add_viewmodel(inner)
        if action == "add_permission":
            return add_permission(inner)
        if action == "add_dependency":
            return add_dependency(inner)
        return {"error": f"acción de componente desconocida: {action}"}
    return {"error": f"dominio android desconocido: {domain}"}
