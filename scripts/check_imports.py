#!/usr/bin/env python3
"""Check for import consistency and missing module references"""

import sys
import ast
from pathlib import Path
from typing import Dict, List, Set


class ImportChecker:
    """Checks import consistency across modules"""
    
    def __init__(self, repo_root: Path = Path(".")):
        self.repo_root = repo_root
        self.imports_by_module: Dict[str, Set[str]] = {}
        self.defined_modules: Set[str] = set()
        self.errors: List[str] = []
        self.warnings: List[str] = []
    
    def find_all_modules(self) -> List[Path]:
        """Find all Python modules in the repository"""
        return list(self.repo_root.rglob("*.py"))
    
    def extract_imports(self, file_path: Path) -> Set[str]:
        """Extract all imports from a Python file"""
        imports = set()
        
        try:
            with open(file_path, 'r') as f:
                tree = ast.parse(f.read())
            
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imports.add(alias.name.split('.')[0])
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        imports.add(node.module.split('.')[0])
        except Exception as e:
            self.errors.append(f"Error parsing {file_path}: {e}")
        
        return imports
    
    def check_module_exists(self, module_name: str) -> bool:
        """Check if a module exists in the repository"""
        # Check if it's a standard library or third-party
        standard_libs = {
            'sys', 'os', 'asyncio', 'logging', 'json', 'time', 'datetime',
            'pathlib', 'typing', 'functools', 'collections', 'hashlib',
            'psutil', 'signal', 'traceback', 'uuid', 're', 'aiofiles',
            'sqlalchemy', 'redis', 'fastapi', 'starlette', 'pydantic',
            'uvicorn', 'aiofiles'
        }
        
        if module_name in standard_libs:
            return True
        
        # Check if it's defined in our repo
        module_path = self.repo_root / module_name.replace('.', '/')
        if module_path.exists() and (module_path.is_file() or (module_path / '__init__.py').exists()):
            return True
        
        # Check in current/relative paths
        for py_file in self.find_all_modules():
            if py_file.stem == module_name.split('.')[-1]:
                return True
        
        return False
    
    def run_checks(self) -> bool:
        """Run all consistency checks"""
        print("🔍 Checking import consistency...\n")
        
        modules = self.find_all_modules()
        print(f"📁 Found {len(modules)} Python files\n")
        
        # First pass: collect all imports
        for module in modules:
            rel_path = module.relative_to(self.repo_root)
            imports = self.extract_imports(module)
            self.imports_by_module[str(rel_path)] = imports
        
        # Second pass: check for undefined imports
        for module_path, imports in self.imports_by_module.items():
            for imp in imports:
                # Skip relative imports and local modules
                if imp.startswith('.'):
                    continue
                
                # Check core modules
                if imp.startswith('core') or imp.startswith('services') or \
                   imp.startswith('infrastructure') or imp.startswith('app'):
                    if not self.check_module_exists(imp):
                        self.errors.append(
                            f"❌ {module_path}: Missing import '{imp}'"
                        )
        
        # Check for missing __init__.py files
        for module in modules:
            parent = module.parent
            init_file = parent / '__init__.py'
            
            # Check if core/ subdirectories have __init__.py
            if 'core' in str(parent) or 'services' in str(parent) or \
               'infrastructure' in str(parent) or 'app' in str(parent):
                if not init_file.exists() and str(parent) != str(self.repo_root):
                    self.warnings.append(
                        f"⚠️  Missing __init__.py in {parent.relative_to(self.repo_root)}"
                    )
        
        # Print results
        if self.errors:
            print("❌ ERRORS:")
            for error in self.errors:
                print(f"  {error}")
            print()
        
        if self.warnings:
            print("⚠️  WARNINGS:")
            for warning in self.warnings:
                print(f"  {warning}")
            print()
        
        if not self.errors and not self.warnings:
            print("✅ All checks passed!\n")
        
        return len(self.errors) == 0


if __name__ == "__main__":
    checker = ImportChecker()
    success = checker.run_checks()
    sys.exit(0 if success else 1)
