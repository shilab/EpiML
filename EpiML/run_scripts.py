import os
import json
import shlex
import subprocess
import pandas as pd
from datetime import datetime, timezone

from flask_login import current_user

from EpiML import app, db, celery

from EpiML.db_tables import User, Job, Model


def create_job_folder(upload_folder='', userid=None, jobid=None):
    # create upload_folder
    if not os.path.exists(upload_folder):
        cmd_args = shlex.split('mkdir ' + upload_folder)
        subprocess.Popen(cmd_args).wait()

    # create user dir
    user_dir = os.path.join(upload_folder, '_'.join(['userid', str(userid)]))
    if not os.path.exists(user_dir):
        cmd_args = shlex.split('mkdir ' + user_dir)
        subprocess.Popen(cmd_args).wait()

    # create job dir
    job_dir = os.path.join(user_dir, '_'.join(['jobid', str(jobid)]))
    if not os.path.exists(job_dir):
        cmd_args = shlex.split('mkdir ' + job_dir)
        subprocess.Popen(cmd_args).wait()

    return job_dir


@celery.task()
def call_train_scripts(jobid, category, method, params=None, job_dir='', x_filename='', y_filename=''):
    print('Background start...')
    job = Job.query.filter_by(id=jobid).first_or_404()
    job.status = 'Running'
    db.session.add(job)
    db.session.commit()

    if method == 'EBEN':
        print('run EBEN')
        with open(os.path.join(job_dir, 'EBEN_train.stdout'), 'w') as EBEN_stdout, \
                open(os.path.join(job_dir, 'EBEN_train.stderr'), 'w') as EBEN_stderr:
            subprocess.run(['Rscript', app.config['EBEN_TRAIN_SCRIPT'], job_dir, x_filename, y_filename,
                            params['fold_number'], params['seed_number']],
                           stdout=EBEN_stdout,
                           stderr=EBEN_stderr)

    if method == 'SSLASSO':
        print('run SSLASSO')
        with open(os.path.join(job_dir, 'SSLASSO_train.stdout'), 'w') as SSLASSO_stdout, \
                open(os.path.join(job_dir, 'SSLASSO_train.stderr'), 'w') as SSLASSO_stderr:
            subprocess.run(['Rscript', app.config['SSLASSO_SCRIPT'], job_dir, x_filename, y_filename,
                            params['fold_number'], params['seed_number']],
                           stdout=SSLASSO_stdout,
                           stderr=SSLASSO_stderr)

    if method == 'LASSO':
        with open(os.path.join(job_dir, 'LASSO_train.stdout'), 'w') as LASSO_stdout, \
                open(os.path.join(job_dir, 'LASSO_train.stderr'), 'w') as LASSO_stderr:
            subprocess.Popen(
                ['Rscript', app.config['LASSO_TRAIN_SCRIPT'], params['alpha'], job_dir, x_filename, y_filename],
                stdout=LASSO_stdout,
                stderr=LASSO_stderr)

    job.status = 'Done'
    job.running_time = str(datetime.now(timezone.utc).replace(tzinfo=None) - job.timestamp)[:-7]
    db.session.add(job)
    db.session.commit()
    print('Background Done!')
