from datetime import date
from typing import Literal, Annotated
from uuid import UUID

from pydantic import BaseModel, Field, StringConstraints, field_validator, model_validator
from psycopg.types.json import Jsonb
from pipeline import copy_audit
from watchlist import active, normalize

Text=Annotated[str,StringConstraints(strip_whitespace=True,min_length=1,max_length=256)]


class Identity(BaseModel):
    name: Text
    date_of_birth: date | None = None
    id_number: Text
    address: Text

    @field_validator("name")
    @classmethod
    def screenable(cls, value):
        if not normalize(value):
            raise ValueError("Name must contain letters or numbers")
        return value


class Owner(BaseModel):
    identity: Identity
    owners: list["Owner"] = Field(default_factory=list,max_length=25)


class Application(BaseModel):
    application_id: UUID
    kind: Literal["person","business"]
    applicant: Identity
    documents: list[Identity] = Field(min_length=1,max_length=12)
    owners: list[Owner] = Field(default_factory=list,max_length=25)

    @model_validator(mode="after")
    def person_fields(self):
        if self.kind=="person" and (self.applicant.date_of_birth is None or self.owners):
            raise ValueError("A person requires a birth date and cannot have a business ownership chain")
        return self


def audit(db,action,payload,case_id=None,transaction_id=None):
    db.execute("""INSERT INTO audit(actor,action,inputs,case_id,transaction_id)
                  VALUES ('kyc-screen-v1',%s,%s,%s,%s)""",
               (action,Jsonb(payload),case_id,transaction_id))


def review(app, snapshot):
    gaps=[]
    for i,doc in enumerate(app.documents):
        for key in Identity.model_fields:
            left,right=getattr(app.applicant,key),getattr(doc,key)
            if key=="name":
                left,right=normalize(left),normalize(right)
            elif key=="address":
                left,right=left.casefold().split(),right.casefold().split()
            if left!=right:
                gaps.append(dict(document=i+1,field=key,reason="Application and document values differ"))
    if app.kind=="business" and not app.owners:
        gaps.append(dict(field="owners",reason="Beneficial ownership details missing"))
    subjects=[]
    def screen(identity,path):
        subjects.append(dict(path=path,**snapshot.screen(identity.name,identity.date_of_birth)))
    screen(app.applicant,"applicant")
    for i,doc in enumerate(app.documents):
        if (doc.name,doc.date_of_birth)!=(app.applicant.name,app.applicant.date_of_birth):
            screen(doc,f"documents[{i}]")
    def walk(owners,path):
        for i,owner in enumerate(owners):
            child=f"{path}[{i}]"
            screen(owner.identity,child)
            walk(owner.owners,child+".owners")
    walk(app.owners,"owners")
    return dict(application_id=str(app.application_id),kind=app.kind,mismatches=gaps,
                screening=subjects,requires_review=bool(gaps or any(s["hits"] for s in subjects)))


def payment_screen(db,row):
    payment_screen_batch(db,[row])


def payment_screen_batch(db,rows):
    """Screen each outbound counterparty once per (account, normalized name, snapshot). Batched for the
    scorer (ADR-032): one insert round trip and one audit round trip for all debits in the batch."""
    debits=[row for row in rows if row["direction"]=="debit"]
    if not debits:
        return
    snapshot=active()
    new=[]
    with db.cursor() as cur:
        cur.executemany("""INSERT INTO screened_counterparties(account,name_key,snapshot)
            VALUES (%s,%s,%s) ON CONFLICT DO NOTHING RETURNING account""",
            [(row["account"],normalize(row["counterparty"]),snapshot.version) for row in debits],returning=True)
        for row in debits:  # one result set per row, in order; a repeat within the batch conflicts
            if cur.fetchone():
                new.append(row)
            cur.nextset()
    copy_audit(db,[("kyc-screen-v1","payment.screened.v1",row["case_id"],row["id"],
                    dict(account=row["account"],**snapshot.screen(row["counterparty"]))) for row in new])
