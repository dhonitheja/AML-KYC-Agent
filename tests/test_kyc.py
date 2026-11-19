import json
import time
import uuid
import urllib.error
import urllib.request

import psycopg
import pytest
from confluent_kafka import Producer

from pipeline import BROKER, DSN, TOPIC, event
from watchlist import active


@pytest.mark.parametrize("name",["Cobalt Meridian Exports","Exports, COBALT-Meridian","Cobalt Meridan Exports","Elara Vespar"])
def test_seeded_names_variants_and_aliases(name):
    hit,=active().screen(name)["hits"]
    assert hit["entry_id"] in {"990001","990002"}
    assert hit["matched_name"] and hit["score"]>=88 and hit["reason"]


def test_clean_name():
    assert active().screen("Juniper Orchard Services")["hits"]==[]


def post(data):
    req=urllib.request.Request("http://api:8000/onboarding",data=json.dumps(data).encode(),
                               headers={"Content-Type":"application/json"})
    with urllib.request.urlopen(req, timeout=10) as response:
        return json.load(response)


def test_onboard_nested_owners_documents_audit_and_replay():
    identity=dict(name="Juniper Orchard Services",id_number="DEMO-001",address="1 Example Road")
    owner=dict(identity=dict(identity,name="Vesperin, Elara",date_of_birth="1982-03-08"))
    application=dict(application_id=str(uuid.uuid4()),kind="business",applicant=identity,
                     documents=[dict(identity,address="2 Example Road")],
                     owners=[dict(identity=dict(identity,name="Sample Holdings"),owners=[owner])])
    result=post(application)
    assert post(application)==result
    assert result["requires_review"] and result["mismatches"][0]["field"]=="address"
    nested=result["screening"][-1]
    assert nested["path"]=="owners[0].owners[0]"
    assert nested["hits"][0]["disposition"]=="corroborated_match"
    with psycopg.connect(DSN) as db:
        actions=dict(db.execute("""SELECT action,count(*) FROM audit WHERE inputs->>'application_id'=%s
                                  GROUP BY action""",(application["application_id"],)).fetchall())
    assert actions=={"kyc.reviewed.v1":1,"onboarding.screened.v1":3}
    application["documents"]=[identity]
    with pytest.raises(urllib.error.HTTPError) as exc:
        post(application)
    assert exc.value.code==409


def test_person_conflicting_dob_and_document_alias():
    person=dict(name="Elara Vesperin",date_of_birth="1999-01-11",id_number="DEMO-002",address="3 Demo Lane")
    result=post(dict(application_id=str(uuid.uuid4()),kind="person",applicant=person,
                     documents=[dict(person,name="Elara Vespar")]))
    assert result["mismatches"][0]["field"]=="name"
    for screen in result["screening"]:
        hit,=screen["hits"]
        assert hit["disposition"]=="conflicting_dob" and "birth dates differ" in hit["reason"]


def test_payment_stream_screens_each_new_counterparty_once():
    run=uuid.uuid4()
    p=Producer({"bootstrap.servers":BROKER})
    for i,name in enumerate(["Cobalt Meridan Exports","Exports, Cobalt Meridan","Juniper Orchard Services"]):
        row=event(run,i,None,True)
        row.update(account=str(run),counterparty=name,direction="debit")
        p.produce(TOPIC,key=row["account"],value=json.dumps(row))
    assert p.flush(15)==0
    deadline=time.monotonic()+45
    with psycopg.connect(DSN,autocommit=True) as db:
        while time.monotonic()<deadline:
            completed=db.execute("SELECT count(*) FROM audit WHERE action='scored.v1' AND inputs->>'run_id'=%s",
                                 (str(run),)).fetchone()[0]
            if completed==3:
                break
            time.sleep(.1)
        assert completed==3
        rows=db.execute("SELECT inputs FROM audit WHERE action='payment.screened.v1' AND inputs->>'account'=%s ORDER BY event_id",
                        (str(run),)).fetchall()
    flagged,clean=[r[0] for r in rows]
    hit,=flagged["hits"]
    assert hit["entry_id"]=="990002" and hit["reason"] and hit["score"]>=88
    assert not clean["hits"]
