"""Check that a model tool call only executes our uploaded runner file once.
No model text or contestant code is evaluated by the web server.
"""
import ast

class UnsafeExecution(ValueError): pass

def authorized_execution(code,path):
    try:
        tree=ast.parse(code)
        if not 1<=len(tree.body)<=3: return False
        values={}; executions=0
        def value(n):
            if isinstance(n,ast.Constant) and isinstance(n.value,str):return ('text',n.value)
            if isinstance(n,ast.Name) and n.id in values:return values[n.id]
            if not isinstance(n,ast.Call):raise UnsafeExecution()
            if isinstance(n.func,ast.Name) and n.func.id=='open':
                if not 1<=len(n.args)<=2 or value(n.args[0])!=('text',path):raise UnsafeExecution()
                if len(n.args)==2 and value(n.args[1])!=('text','r'):raise UnsafeExecution()
                if any(k.arg!='encoding' or value(k.value)!=('text','utf-8') for k in n.keywords):raise UnsafeExecution()
                return ('handle',path)
            if isinstance(n.func,ast.Attribute) and n.func.attr=='read':
                if n.args or n.keywords or value(n.func.value)!=('handle',path):raise UnsafeExecution()
                return ('source',path)
            if isinstance(n.func,ast.Name) and n.func.id=='compile':
                if len(n.args)!=3 or n.keywords or value(n.args[0])!=('source',path) or value(n.args[1])!=('text',path) or value(n.args[2])!=('text','exec'):raise UnsafeExecution()
                return ('compiled',path)
            if isinstance(n.func,ast.Name) and n.func.id=='exec':
                if len(n.args)!=1 or n.keywords or value(n.args[0]) not in (('source',path),('compiled',path)):raise UnsafeExecution()
                return ('execute',path)
            if isinstance(n.func,ast.Attribute) and n.func.attr=='run_path' and value(n.func.value)==('module','runpy'):
                if len(n.args)!=1 or value(n.args[0])!=('text',path):raise UnsafeExecution()
                if any(k.arg!='run_name' or value(k.value)!=('text','__main__') for k in n.keywords):raise UnsafeExecution()
                return ('execute',path)
            raise UnsafeExecution()
        def run(stmt):
            nonlocal executions
            if isinstance(stmt,ast.Import) and len(stmt.names)==1 and stmt.names[0].name=='runpy' and not stmt.names[0].asname:
                values['runpy']=('module','runpy');return
            if isinstance(stmt,ast.Assign) and len(stmt.targets)==1 and isinstance(stmt.targets[0],ast.Name):
                name=stmt.targets[0].id
                if name in ('open','exec','compile','runpy') or name.startswith('__'):raise UnsafeExecution()
                item=value(stmt.value)
                if item[0]=='execute':raise UnsafeExecution()
                values[name]=item;return
            if isinstance(stmt,ast.Expr):
                if value(stmt.value)!=('execute',path):raise UnsafeExecution()
                executions+=1;return
            if isinstance(stmt,ast.With) and len(stmt.items)==1 and len(stmt.body)==1:
                item=stmt.items[0]
                if not isinstance(item.optional_vars,ast.Name) or value(item.context_expr)!=('handle',path):raise UnsafeExecution()
                values[item.optional_vars.id]=('handle',path)
                run(stmt.body[0]);return
            raise UnsafeExecution()
        for statement in tree.body:run(statement)
        return executions==1
    except (SyntaxError,UnsafeExecution,RecursionError,TypeError,ValueError):return False
