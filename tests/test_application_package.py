import tempfile
import unittest
import zipfile
from pathlib import Path

from tools.build_release import application_files, create_zip
from tools.prepare_public_release import candidates


class ApplicationPackageTests(unittest.TestCase):
    def test_package_omits_development_files_without_changing_source_export(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            retained=('main.py','core/app.py','core/spatial/vendor/package/build/three.module.js',
                      'tools/research_worker.py','tools/provision_browser_runtime.py',
                      'resources/guide.md','memory/__init__.py','config/defaults.json',
                      'LICENSE','NOTICE.md','requirements-win.lock')
            omitted=('tests/test_app.py','docs/audit.md','validation/essential-plugins-guide.md',
                     '.github/workflows/check.yml','.gitignore','.gitattributes')
            for name in retained+omitted:
                path=root/name
                path.parent.mkdir(parents=True,exist_ok=True)
                path.write_text('fixture',encoding='utf-8')
            public={p.as_posix() for p in candidates(root)}
            package=application_files(root)
            self.assertTrue(set(omitted)<=public)
            self.assertEqual({p.as_posix() for p in package},set(retained))
            destination=root/'application.zip'
            create_zip(destination,root,package)
            with zipfile.ZipFile(destination) as archive:
                self.assertIsNone(archive.testzip())
                self.assertEqual(set(archive.namelist()),set(retained))
            self.assertTrue(all((root/name).is_file() for name in omitted))


if __name__=='__main__':
    unittest.main()
