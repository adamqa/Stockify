#!/usr/bin/env python
"""
Stockify Deployment Readiness Checker
Run this before deploying to ensure everything works perfectly
Usage: python deployment_checker.py
"""

import os
import sys
import django
import subprocess
import requests
import json
from pathlib import Path

# Colors for output
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    RESET = '\033[0m'
    BOLD = '\033[1m'

def print_success(msg):
    print(f"{Colors.GREEN}✅ {msg}{Colors.RESET}")

def print_error(msg):
    print(f"{Colors.RED}❌ {msg}{Colors.RESET}")

def print_warning(msg):
    print(f"{Colors.YELLOW}⚠️  {msg}{Colors.RESET}")

def print_info(msg):
    print(f"{Colors.BLUE}ℹ️  {msg}{Colors.RESET}")

def print_header(msg):
    print(f"\n{Colors.CYAN}{Colors.BOLD}{'='*60}{Colors.RESET}")
    print(f"{Colors.CYAN}{Colors.BOLD}{msg:^60}{Colors.RESET}")
    print(f"{Colors.CYAN}{Colors.BOLD}{'='*60}{Colors.RESET}\n")

class DeploymentChecker:
    def __init__(self):
        self.base_dir = Path(__file__).resolve().parent
        self.errors = []
        self.warnings = []
        self.passed = []
        
    def check_python_version(self):
        """Check Python version"""
        print_info("Checking Python version...")
        version = sys.version_info
        if version.major >= 3 and version.minor >= 8:
            print_success(f"Python {version.major}.{version.minor}.{version.micro}")
            self.passed.append("Python version")
        else:
            print_error(f"Python {version.major}.{version.minor} (need 3.8+)")
            self.errors.append("Python version too old")
    
    def check_requirements(self):
        """Check if all requirements are installed"""
        print_info("Checking requirements...")
        req_file = self.base_dir / "requirements.txt"
        if not req_file.exists():
            print_warning("requirements.txt not found")
            self.warnings.append("requirements.txt missing")
            return
        
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pip", "check"],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                print_success("All requirements installed")
                self.passed.append("Requirements")
            else:
                print_warning("Some requirements may be missing")
                print(result.stdout)
                self.warnings.append("Missing requirements")
        except Exception as e:
            print_error(f"Could not check requirements: {e}")
    
    def check_environment_variables(self):
        """Check essential environment variables"""
        print_info("Checking environment variables...")
        
        essential_vars = [
            'SECRET_KEY',
            'DATABASE_URL'
        ]
        
        optional_vars = [
            'DEBUG',
            'ALLOWED_HOSTS',
            'DJANGO_SETTINGS_MODULE'
        ]
        
        for var in essential_vars:
            if os.environ.get(var):
                print_success(f"{var} is set")
                self.passed.append(f"ENV: {var}")
            else:
                print_warning(f"{var} is not set (required for production)")
                self.warnings.append(f"{var} not set")
        
        for var in optional_vars:
            if os.environ.get(var):
                print_success(f"{var} is set")
            else:
                print_info(f"{var} is not set (using default)")
        
        # Check for Railway-specific variables
        if os.environ.get('RAILWAY_ENVIRONMENT'):
            print_success("Railway environment detected")
            self.passed.append("Railway deployment")
    
    def check_django_configuration(self):
        """Check Django settings"""
        print_info("Checking Django configuration...")
        
        try:
            os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'back.settings')
            django.setup()
            from django.conf import settings
            
            # Check DEBUG mode
            if settings.DEBUG:
                print_warning("DEBUG=True (should be False in production)")
                self.warnings.append("DEBUG=True in production")
            else:
                print_success("DEBUG=False")
            
            # Check ALLOWED_HOSTS
            if settings.ALLOWED_HOSTS:
                print_success(f"ALLOWED_HOSTS configured: {settings.ALLOWED_HOSTS}")
                self.passed.append("ALLOWED_HOSTS configured")
            else:
                print_error("ALLOWED_HOSTS is empty!")
                self.errors.append("ALLOWED_HOSTS empty")
            
            # Check SECRET_KEY
            if settings.SECRET_KEY and 'django-insecure' not in settings.SECRET_KEY:
                print_success("SECRET_KEY is properly configured")
                self.passed.append("SECRET_KEY set")
            elif 'django-insecure' in settings.SECRET_KEY:
                print_warning("Using insecure SECRET_KEY (change for production)")
                self.warnings.append("Insecure SECRET_KEY")
            
            # Check static files
            if hasattr(settings, 'STATIC_ROOT') and settings.STATIC_ROOT:
                print_success(f"STATIC_ROOT: {settings.STATIC_ROOT}")
            else:
                print_warning("STATIC_ROOT not set")
                
        except Exception as e:
            print_error(f"Django configuration error: {e}")
            self.errors.append(f"Django config: {e}")
    
    def check_database(self):
        """Check database connection and migrations"""
        print_info("Checking database...")
        
        try:
            from django.db import connection
            from django.db.migrations.executor import MigrationExecutor
            
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
            print_success("Database connection successful")
            self.passed.append("Database connected")
            
            # Check migrations
            executor = MigrationExecutor(connection)
            if executor.migration_plan(executor.loader.graph.leaf_nodes()):
                print_warning("Unapplied migrations found. Run: python manage.py migrate")
                self.warnings.append("Unapplied migrations")
            else:
                print_success("All migrations applied")
                self.passed.append("Migrations applied")
                
        except Exception as e:
            print_error(f"Database error: {e}")
            self.errors.append(f"Database: {e}")
    
    def check_migrations(self):
        """Check if migrations are created"""
        print_info("Checking migrations...")
        
        try:
            result = subprocess.run(
                [sys.executable, "manage.py", "makemigrations", "--check", "--dry-run"],
                capture_output=True,
                text=True,
                cwd=self.base_dir
            )
            
            if "No changes detected" in result.stdout:
                print_success("No missing migrations")
                self.passed.append("Migrations up to date")
            else:
                print_warning("Missing migrations detected. Run: python manage.py makemigrations")
                self.warnings.append("Missing migrations")
        except Exception as e:
            print_error(f"Could not check migrations: {e}")
    
    def check_static_files(self):
        """Check static files configuration"""
        print_info("Checking static files...")
        
        try:
            result = subprocess.run(
                [sys.executable, "manage.py", "collectstatic", "--dry-run", "--noinput"],
                capture_output=True,
                text=True,
                cwd=self.base_dir
            )
            
            if result.returncode == 0:
                print_success("Static files configured correctly")
                self.passed.append("Static files OK")
            else:
                print_warning("Static files may not be configured correctly")
                self.warnings.append("Static files issue")
        except Exception as e:
            print_error(f"Static files error: {e}")
    
    def check_urls(self):
        """Check if URLs are configured"""
        print_info("Checking URL configuration...")
        
        try:
            from django.urls import get_resolver
            resolver = get_resolver()
            url_count = len(resolver.url_patterns)
            print_success(f"URL patterns loaded: {url_count}")
            self.passed.append(f"{url_count} URL patterns")
        except Exception as e:
            print_error(f"URL configuration error: {e}")
            self.errors.append(f"URLs: {e}")
    
    def check_admin(self):
        """Check admin interface"""
        print_info("Checking admin interface...")
        
        try:
            from django.contrib.admin import site
            registered_models = len(site._registry)
            print_success(f"Admin registered models: {registered_models}")
        except Exception as e:
            print_error(f"Admin configuration error: {e}")
    
    def check_security(self):
        """Check security settings"""
        print_info("Checking security settings...")
        
        try:
            from django.conf import settings
            
            security_headers = [
                ('SECURE_BROWSER_XSS_FILTER', True),
                ('SECURE_CONTENT_TYPE_NOSNIFF', True),
                ('X_FRAME_OPTIONS', 'DENY'),
                ('CSRF_COOKIE_SECURE', True),
                ('SESSION_COOKIE_SECURE', True),
            ]
            
            for header, expected in security_headers:
                if hasattr(settings, header):
                    if getattr(settings, header) == expected:
                        print_success(f"{header} correctly set")
                    else:
                        print_warning(f"{header} should be {expected}")
                        self.warnings.append(f"{header} misconfigured")
                else:
                    print_warning(f"{header} not set")
                    self.warnings.append(f"{header} missing")
                    
        except Exception as e:
            print_error(f"Security check error: {e}")
    
    def test_api_endpoints(self):
        """Test critical API endpoints"""
        print_info("Testing API endpoints...")
        
        endpoints = [
            '/admin/',
            '/api/health/',
            '/api/home/',
        ]
        
        for endpoint in endpoints:
            try:
                response = requests.get(f"http://localhost:8000{endpoint}", timeout=5)
                if response.status_code == 200:
                    print_success(f"{endpoint} -> {response.status_code}")
                    self.passed.append(f"API: {endpoint}")
                elif response.status_code in [301, 302]:
                    print_warning(f"{endpoint} -> {response.status_code} (redirect)")
                else:
                    print_warning(f"{endpoint} -> {response.status_code}")
                    self.warnings.append(f"API {endpoint}: {response.status_code}")
            except requests.ConnectionError:
                print_warning(f"Server not running at localhost:8000")
                self.warnings.append("Django server not running")
                break
            except Exception as e:
                print_error(f"Could not test {endpoint}: {e}")
    
    def check_gunicorn(self):
        """Check if gunicorn is installed for production"""
        print_info("Checking production server...")
        
        try:
            import gunicorn
            print_success("Gunicorn installed")
            self.passed.append("Gunicorn")
        except ImportError:
            print_warning("Gunicorn not installed (recommended for production)")
            self.warnings.append("Gunicorn missing")
    
    def create_deployment_report(self):
        """Generate deployment report"""
        print_header("DEPLOYMENT READINESS REPORT")
        
        total_checks = len(self.passed) + len(self.warnings) + len(self.errors)
        
        print(f"{Colors.BOLD}Summary:{Colors.RESET}")
        print(f"  ✅ Passed: {len(self.passed)}")
        print(f"  ⚠️  Warnings: {len(self.warnings)}")
        print(f"  ❌ Errors: {len(self.errors)}")
        
        if self.errors:
            print(f"\n{Colors.RED}{Colors.BOLD}❌ CRITICAL ERRORS TO FIX BEFORE DEPLOYMENT:{Colors.RESET}")
            for error in self.errors:
                print(f"  • {error}")
        
        if self.warnings:
            print(f"\n{Colors.YELLOW}{Colors.BOLD}⚠️  WARNINGS TO REVIEW:{Colors.RESET}")
            for warning in self.warnings:
                print(f"  • {warning}")
        
        if not self.errors and not self.warnings:
            print(f"\n{Colors.GREEN}{Colors.BOLD}🎉 PERFECT! Your app is ready for deployment!{Colors.RESET}")
            return True
        elif not self.errors:
            print(f"\n{Colors.YELLOW}{Colors.BOLD}⚠️  Your app can be deployed but has warnings to address.{Colors.RESET}")
            return True
        else:
            print(f"\n{Colors.RED}{Colors.BOLD}❌ Your app has critical errors that must be fixed before deployment.{Colors.RESET}")
            return False
    
    def run_all_checks(self):
        """Run all checks"""
        print_header("STOCKIFY DEPLOYMENT READINESS CHECKER")
        
        self.check_python_version()
        self.check_requirements()
        self.check_environment_variables()
        self.check_django_configuration()
        self.check_database()
        self.check_migrations()
        self.check_static_files()
        self.check_urls()
        self.check_admin()
        self.check_security()
        self.check_gunicorn()
        
        # Optional: Test API endpoints (requires server running)
        # self.test_api_endpoints()
        
        return self.create_deployment_report()

def main():
    checker = DeploymentChecker()
    is_ready = checker.run_all_checks()
    
    print(f"\n{Colors.CYAN}{'='*60}{Colors.RESET}")
    if is_ready:
        print(f"{Colors.GREEN}✅ Deployment readiness check complete!{Colors.RESET}")
        print(f"\n{Colors.BOLD}Next steps:{Colors.RESET}")
        print("  1. git add . && git commit -m \"Ready for deployment\"")
        print("  2. git push railway main")
        print("  3. railway logs --tail 50")
    else:
        print(f"{Colors.RED}❌ Please fix the errors above before deploying{Colors.RESET}")
    
    sys.exit(0 if is_ready else 1)

if __name__ == "__main__":
    main()