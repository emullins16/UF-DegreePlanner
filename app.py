from flask import Flask, render_template, jsonify, request
import csv
import os

app = Flask(__name__)

# Degree templates data
DEGREE_TEMPLATES = {
    'Computer Science': {
        'core_courses': ['COP 3502C', 'COP 3503C', 'COT 3100', 'COP 3530', 
                       'CDA 3101', 'COP 4600', 'CEN 3031'],
        'description': 'CS Core Curriculum'
    },
    'Computer Engineering': {
        'core_courses': ['EEL 3111C', 'EEL 3701C', 'COP 3530', 'EEL 4712C', 
                       'CDA 3101', 'COP 4600', 'CEN 4907C'],
        'description': 'CpE Core Curriculum'
    },
    'Electrical Engineering': {
        'core_courses': ['EEL 3111C', 'EEL 3112', 'EEL 3701C', 'EEL 3135', 
                       'EEE 3308C', 'EEL 4712C', 'EEL 3923C'],
        'description': 'EE Core Curriculum'
    },
    'Biomedical Engineering': {
        'core_courses': ['BME 1008', 'BME 3060', 'BME 3053C', 'BME 3101', 
                       'BME 4311', 'BME 4503C', 'BME 4882', 'BME 4883'],
        'description': 'BME Core Curriculum'
    },
     'Mechanical Engineering': {
        'core_courses': ['EML 2023', 'EML 3100', 'EGM 3520', 'EGN 3353C', 
                       'EML 4140', 'EML 4312', 'EML 4501', 'EML 4502'],
        'description': 'ME Core Curriculum'
    },
    'Aerospace Engineering': {
        'core_courses': ['EAS 2011', 'EAS 4101', 'EAS 4200', 'EAS 4300', 
                       'EAS 4510', 'EAS 4700', 'EAS 4710'],
        'description': 'AE Core Curriculum'
    },
    'Chemical Engineering': {
        'core_courses': ['ECH 3023', 'ECH 3101', 'ECH 3264', 'ECH 4123', 
                       'ECH 4403', 'ECH 4504', 'ECH 4644'],
        'description': 'ChE Core Curriculum'
    },
    'Civil Engineering': {
        'core_courses': ['CGN 3421', 'CES 3102', 'CWR 3201', 'CEG 4011', 
                       'CES 4605', 'CES 4702', 'CGN 4806'],
        'description': 'CE Core Curriculum'
    },
    'Environmental Engineering': {
        'core_courses': ['ENV 3001', 'ENV 3000', 'ENV 4453', 'ENV 4454', 
                       'ENV 4009', 'ENV 4514C', 'ENV 4892', 'ENV 4893'],
        'description': 'EnvE Core Curriculum'
    },
    'Industrial & Systems Engineering': {
        'core_courses': ['ESI 3215C', 'ESI 3327C', 'ESI 3312', 'ESI 4313', 
                       'ESI 4221C', 'EIN 3354', 'EIN 4335'],
        'description': 'ISE Core Curriculum'
    },
    'Materials Science & Engineering': {
        'core_courses': ['EMA 3010', 'EMA 3011', 'EMA 3050', 'EMA 3066', 'EMA 3413', 
                       'EMA 4120', 'EMA 4223', 'EMA 4314', 'EMA 4714'],
        'description': 'MSE Core Curriculum'
    }
}

# Load courses from CSV
def load_courses():
    courses = []
    csv_path = 'courses.csv'
    if os.path.exists(csv_path):
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                courses.append(row)
    return courses

COURSES = load_courses()

def parse_prerequisites(prereq_str):
    if not prereq_str or prereq_str.strip() == '':
        return []
    # Split by semicolon and clean up
    prereqs = [p.strip() for p in prereq_str.split(';')]
    return [p for p in prereqs if p]

def build_tree(course_code, seen=None, path=None, depth=0, max_depth=15):
    if seen is None:
        seen = set()
    if path is None:
        path = []
    
    # Prevent infinite recursion
    if depth > max_depth:
        return {
            'code': course_code,
            'name': 'Max depth reached',
            'depth': depth,
            'is_truncated': True,
            'prerequisites': []
        }
    
    # Check for circular dependency (same path)
    if course_code in path:
        return {
            'code': course_code,
            'name': 'CIRCULAR DEPENDENCY',
            'is_circular': True,
            'depth': depth,
            'prerequisites': []
        }

    # If this course was already expanded elsewhere in the forest, mark as duplicate
    if course_code in seen:
        return {
            'code': course_code,
            'name': 'Duplicate reference',
            'is_duplicate': True,
            'depth': depth,
            'prerequisites': []
        }
    
    # Find the course
    course = next((c for c in COURSES if c['coursecode'] == course_code), None)
    if not course:
        return {
            'code': course_code,
            'name': 'Course Not Found',
            'is_missing': True,
            'depth': depth,
            'prerequisites': []
        }
    
    # Add to visited path and global seen set
    path_copy = path.copy()
    path_copy.append(course_code)
    seen.add(course_code)
    
    prereqs = parse_prerequisites(course.get('prereqcode', ''))
    coreqs = parse_prerequisites(course.get('coreqcode', ''))
    
    # Check if this is a foundation course (no prerequisites)
    is_foundation = len(prereqs) == 0
    
    tree = {
        'code': course_code,
        'name': course.get('name', ''),
        'department': course.get('department', ''),
        'corequisites': coreqs,
        'depth': depth,
        'is_foundation': is_foundation,
        'prerequisites': [build_tree(p, seen, path_copy, depth + 1, max_depth) for p in prereqs]
    }
    
    return tree


def build_forest(course_codes, max_depth=15):
    seen = set()
    children = [build_tree(code, seen=seen, path=[], depth=1, max_depth=max_depth) for code in course_codes]
    return {
        'code': 'ROOT',
        'name': 'Selected Courses',
        'department': '',
        'corequisites': [],
        'depth': 0,
        'is_root': True,
        'prerequisites': children
    }

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/courses')
def get_courses():
    search = request.args.get('search', '').lower()
    dept = request.args.get('department', '')
    
    filtered = COURSES
    
    if search:
        filtered = [c for c in filtered if 
                   search in c.get('coursecode', '').lower() or
                   search in c.get('name', '').lower()]
    
    if dept:
        filtered = [c for c in filtered if c.get('department', '') == dept]
    
    return jsonify(filtered)

@app.route('/api/departments')
def get_departments():
    depts = sorted(set(c.get('department', '') for c in COURSES if c.get('department')))
    return jsonify(depts)

@app.route('/api/tree/<course_code>')
def get_tree(course_code):
    tree = build_tree(course_code)
    return jsonify(tree)

@app.route('/api/degree-templates')
def get_degree_templates():
    return jsonify(DEGREE_TEMPLATES)

@app.route('/api/degree-tree/<degree_name>')
def get_degree_tree(degree_name):
    if degree_name not in DEGREE_TEMPLATES:
        return jsonify({'error': 'Degree not found'}), 404
    
    courses = DEGREE_TEMPLATES[degree_name]['core_courses']
    tree = build_forest(courses)
    
    return jsonify({
        'degree': degree_name,
        'description': DEGREE_TEMPLATES[degree_name]['description'],
        'tree': tree
    })

if __name__ == '__main__':
    app.run(debug=True, port=5000)