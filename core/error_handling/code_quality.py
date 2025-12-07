"""Code quality and maintainability utilities"""
import logging
import ast
from typing import List, Dict, Optional
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

class CodeAnalyzer:
    """Analyze code for quality metrics"""
    
    @staticmethod
    def calculate_complexity(code: str) -> Dict:
        """Calculate cyclomatic complexity"""
        try:
            tree = ast.parse(code)
            
            class ComplexityVisitor(ast.NodeVisitor):
                def __init__(self):
                    self.complexity = 1
                    self.functions = 0
                    self.classes = 0
                
                def visit_If(self, node):
                    self.complexity += 1
                    self.generic_visit(node)
                
                def visit_For(self, node):
                    self.complexity += 1
                    self.generic_visit(node)
                
                def visit_While(self, node):
                    self.complexity += 1
                    self.generic_visit(node)
                
                def visit_ExceptHandler(self, node):
                    self.complexity += 1
                    self.generic_visit(node)
                
                def visit_FunctionDef(self, node):
                    self.functions += 1
                    self.generic_visit(node)
                
                def visit_ClassDef(self, node):
                    self.classes += 1
                    self.generic_visit(node)
            
            visitor = ComplexityVisitor()
            visitor.visit(tree)
            
            return {
                "cyclomatic_complexity": visitor.complexity,
                "functions": visitor.functions,
                "classes": visitor.classes,
                "quality_score": max(0, 100 - (visitor.complexity * 5))
            }
        except Exception as e:
            logger.error(f"Failed to calculate complexity: {e}")
            return {}
    
    @staticmethod
    def analyze_imports(code: str) -> Dict:
        """Analyze import statements"""
        try:
            tree = ast.parse(code)
            imports = []
            
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imports.append(alias.name)
                elif isinstance(node, ast.ImportFrom):
                    for alias in node.names:
                        imports.append(f"{node.module}.{alias.name}")
            
            return {
                "total_imports": len(imports),
                "unique_imports": len(set(imports)),
                "imports": imports
            }
        except Exception as e:
            logger.error(f"Failed to analyze imports: {e}")
            return {}

class DocumentationAnalyzer:
    """Analyze documentation coverage"""
    
    @staticmethod
    def check_docstring_coverage(code: str) -> Dict:
        """Check docstring coverage percentage"""
        try:
            tree = ast.parse(code)
            
            total_functions = 0
            documented_functions = 0
            total_classes = 0
            documented_classes = 0
            
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    total_functions += 1
                    if ast.get_docstring(node):
                        documented_functions += 1
                elif isinstance(node, ast.ClassDef):
                    total_classes += 1
                    if ast.get_docstring(node):
                        documented_classes += 1
            
            func_coverage = (
                (documented_functions / total_functions * 100)
                if total_functions > 0 else 0
            )
            class_coverage = (
                (documented_classes / total_classes * 100)
                if total_classes > 0 else 0
            )
            
            return {
                "function_coverage": f"{func_coverage:.1f}%",
                "class_coverage": f"{class_coverage:.1f}%",
                "functions": {
                    "total": total_functions,
                    "documented": documented_functions
                },
                "classes": {
                    "total": total_classes,
                    "documented": documented_classes
                }
            }
        except Exception as e:
            logger.error(f"Failed to check docstring coverage: {e}")
            return {}

class StyleChecker:
    """Check code style and conventions"""
    
    @staticmethod
    def check_naming_conventions(code: str) -> List[str]:
        """Check PEP8 naming conventions"""
        issues = []
        try:
            tree = ast.parse(code)
            
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    if not node.name.islower() and not node.name.startswith("_"):
                        issues.append(f"Function '{node.name}' should be lowercase")
                
                elif isinstance(node, ast.ClassDef):
                    if not node.name[0].isupper():
                        issues.append(f"Class '{node.name}' should be CamelCase")
        
        except Exception as e:
            logger.error(f"Failed to check naming conventions: {e}")
        
        return issues
    
    @staticmethod
    def check_line_length(code: str, max_length: int = 100) -> List[str]:
        """Check for lines exceeding max length"""
        issues = []
        for i, line in enumerate(code.split('\n'), 1):
            if len(line) > max_length:
                issues.append(f"Line {i} exceeds {max_length} characters ({len(line)} chars)")
        
        return issues[:10]  # Return first 10 issues

class RefactoringHelper:
    """Suggest refactoring opportunities"""
    
    @staticmethod
    def find_duplicate_code(functions: List[str]) -> List[str]:
        """Find potentially duplicate code patterns"""
        duplicates = []
        seen = {}
        
        for func in functions:
            if func in seen:
                duplicates.append(f"Duplicate found: {func}")
            seen[func] = seen.get(func, 0) + 1
        
        return duplicates
    
    @staticmethod
    def suggest_refactoring(code: str) -> List[str]:
        """Suggest refactoring opportunities"""
        suggestions = []
        
        # Check for long functions
        lines = code.split('\n')
        if len(lines) > 200:
            suggestions.append("Consider breaking this file into smaller modules")
        
        # Check for deep nesting
        max_indent = max(
            (len(line) - len(line.lstrip())) // 4
            for line in lines if line.strip()
        )
        if max_indent > 4:
            suggestions.append("Consider reducing nesting depth")
        
        return suggestions

class MetricsCollector:
    """Collect code quality metrics"""
    
    def __init__(self):
        self.metrics_history = []
    
    def collect_metrics(self, code: str, filename: str = "unknown") -> Dict:
        """Collect all code quality metrics"""
        metrics = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "filename": filename,
            "complexity": CodeAnalyzer.calculate_complexity(code),
            "imports": CodeAnalyzer.analyze_imports(code),
            "documentation": DocumentationAnalyzer.check_docstring_coverage(code),
            "style_issues": StyleChecker.check_naming_conventions(code),
            "long_lines": StyleChecker.check_line_length(code),
            "refactoring_suggestions": RefactoringHelper.suggest_refactoring(code)
        }
        
        self.metrics_history.append(metrics)
        
        # Keep only last 100 entries
        if len(self.metrics_history) > 100:
            self.metrics_history = self.metrics_history[-100:]
        
        return metrics
    
    def get_quality_report(self) -> Dict:
        """Generate quality report"""
        if not self.metrics_history:
            return {"message": "No metrics collected yet"}
        
        latest = self.metrics_history[-1]
        complexity = latest["complexity"].get("quality_score", 0)
        doc_coverage = float(
            latest["documentation"].get("function_coverage", "0%").rstrip("%")
        ) / 100
        
        overall_score = (complexity + doc_coverage * 100) / 2
        
        return {
            "overall_score": f"{overall_score:.1f}/100",
            "latest_metrics": latest,
            "history_count": len(self.metrics_history)
        }

# Global instance
metrics_collector = MetricsCollector()
