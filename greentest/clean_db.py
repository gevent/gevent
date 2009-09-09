#!/usr/bin/python
from record_results import get_results_db, sqlite3

if __name__=='__main__':
    c = sqlite3.connect(get_results_db())
    c.execute('delete from testresult where changeset glob "*+"')
    c.commit()

 
