"""Train portable logistic models offline; no Streamlit or visitor-side training.

Latest 20% of unique cases (by term, then name) are held out before fitting.
The browser uses the exported coefficients; Python remains a build dependency only.
"""
import argparse
import json
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, log_loss

ROOT = Path(__file__).resolve().parents[1]
FEATURES = ['circuit', 'issue_area', 'n_conservative', 'term_year_norm']


def fit(frame, target):
    pre = ColumnTransformer([('cat', OneHotEncoder(handle_unknown='ignore'), ['circuit','issue_area']), ('num', StandardScaler(), ['n_conservative','term_year_norm'])])
    pipeline = Pipeline([('pre', pre), ('classifier', LogisticRegression(C=.8, max_iter=2000, random_state=42))])
    pipeline.fit(frame[FEATURES], frame[target])
    return pipeline


def portable(pipeline):
    pre, model = pipeline.named_steps['pre'], pipeline.named_steps['classifier']
    return {'categories': [v.tolist() for v in pre.named_transformers_['cat'].categories_], 'mean': pre.named_transformers_['num'].mean_.tolist(), 'scale': pre.named_transformers_['num'].scale_.tolist(), 'classes': model.classes_.tolist(), 'coef': model.coef_.tolist(), 'intercept': model.intercept_.tolist()}


def train(output):
    frame = pd.read_csv(ROOT/'data/scotus_training_data.csv')
    frame['term_year_norm'] = (frame['term'] - 2005) / 10
    frame['case_key'] = frame['term'].astype(str) + ':' + frame['case'] + ':' + frame['docket'].fillna('').astype(str)
    unique = frame.drop_duplicates('case_key').sort_values(['term','case_key'])
    boundary = max(1,int(len(unique)*.8))
    train_keys = set(unique.iloc[:boundary]['case_key'])
    train, holdout = unique[unique['case_key'].isin(train_keys)], unique[~unique['case_key'].isin(train_keys)]
    if holdout.empty or train['outcome'].nunique()<2:
        raise ValueError('Need enough distinct training and held-out cases with both outcomes.')
    evaluated = fit(train, 'outcome')
    probabilities = evaluated.predict_proba(holdout[FEATURES])
    metrics = {'training_cases':len(train),'held_out_cases':len(holdout),'held_out_accuracy':round(accuracy_score(holdout.outcome,evaluated.predict(holdout[FEATURES])),4),'held_out_log_loss':round(log_loss(holdout.outcome,probabilities,labels=evaluated.classes_),4),'majority_class_accuracy':round(float((holdout.outcome==train.outcome.mode().iloc[0]).mean()),4),'held_out_terms':sorted(holdout.term.unique().tolist())}
    # Refit the published model on training cases only, keeping the holdout honest.
    result={'description':'Offline logistic regression on case-level Oyez features. Latest 20% of cases held out; no vote-row leakage. Probabilities are not externally calibrated. Petitioner category is used only in the statistical baseline. SG and circuit-split adjustments are heuristic.', 'metrics':metrics,'outcome':portable(evaluated),'split':None,'justices':{},'referenceTerm':int(frame.term.max()),'fixtures':[]}
    split_frame = train.dropna(subset=['split'])
    if split_frame['split'].nunique()>1:
        result['split'] = portable(fit(split_frame,'split'))
    for name, group in frame[frame.case_key.isin(train_keys)].groupby('justice'):
        if len(group)>=30 and group['is_majority'].nunique()==2:
            result['justices'][name]=portable(fit(group,'is_majority'))
    for _,row in holdout.head(12).iterrows():
        result['fixtures'].append({'input':{'circuit':row.circuit,'issue':row.issue_area,'conservatives':int(row.n_conservative),'term':int(row.term)},'probability':float(evaluated.predict_proba(pd.DataFrame([row])[FEATURES])[0][list(evaluated.classes_).index(1)])})
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(result,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
    print(json.dumps(metrics,indent=2))
    print('Wrote',output)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'data/web_model.json')
    train(parser.parse_args().output)
