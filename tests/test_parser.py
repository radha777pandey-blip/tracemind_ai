import pytest
from tracemind.ingestion.parser import CodeParser

def test_python_ast_parsing():
    code = '''import os
from database.connection import get_db, BaseConnection

class BaseModel:
    """Base model representation."""
    pass

class User(BaseModel):
    """User representation."""
    def __init__(self, username: str):
        self.username = username

    def save(self) -> bool:
        db = get_db()
        return True

def create_user(username: str) -> User:
    """Factory function to create user."""
    user = User(username)
    user.save()
    return user
'''

    result = CodeParser.parse_file('auth/models.py', code, 'python')
    assert result.syntax_valid is True
    assert len(result.entities) == 5  # BaseModel, User, __init__, save, create_user

    entities_by_name = {e.name: e for e in result.entities}
    assert 'BaseModel' in entities_by_name
    assert entities_by_name['BaseModel'].entity_type == 'class'
    assert entities_by_name['BaseModel'].docstring == 'Base model representation.'

    assert 'User' in entities_by_name
    assert entities_by_name['User'].entity_type == 'class'
    assert entities_by_name['User'].docstring == 'User representation.'

    assert 'save' in entities_by_name
    assert entities_by_name['save'].entity_type == 'method'
    assert entities_by_name['save'].parent_name == 'User'

    assert 'create_user' in entities_by_name
    assert entities_by_name['create_user'].entity_type == 'function'
    assert entities_by_name['create_user'].docstring == 'Factory function to create user.'

    # Dependencies check
    import_targets = {d.target_name for d in result.dependencies if d.relation_type == 'imports'}
    assert 'os' in import_targets
    assert 'database.connection.get_db' in import_targets
    assert 'database.connection.BaseConnection' in import_targets

    inherits_targets = {d.target_name for d in result.dependencies if d.relation_type == 'inherits'}
    assert 'BaseModel' in inherits_targets

    call_targets = {d.target_name for d in result.dependencies if d.relation_type == 'calls'}
    assert 'get_db' in call_targets
    assert 'User' in call_targets
    assert 'user.save' in call_targets

def test_python_syntax_error():
    broken_code = 'def bad_func(:\n    pass'
    result = CodeParser.parse_file('broken.py', broken_code, 'python')
    assert result.syntax_valid is False
    assert result.error_message is not None

def test_javascript_parsing():
    js_code = '''import { getDb } from './database';
const config = require('./config');

class AuthService extends BaseService {
    constructor() {}
}

function verifyToken(token) {
    return true;
}

const loginUser = (user, pass) => {
    return false;
};
'''
    result = CodeParser.parse_file('services/auth.js', js_code, 'javascript')
    assert result.syntax_valid is True
    assert len(result.entities) >= 3

    names = {e.name for e in result.entities}
    assert 'AuthService' in names
    assert 'verifyToken' in names
    assert 'loginUser' in names

    deps = {d.target_name for d in result.dependencies}
    assert './database' in deps
    assert './config' in deps
    assert 'BaseService' in deps
