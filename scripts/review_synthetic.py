#!/usr/bin/env python3
"""Public R8622 synthetic-only review. Stdlib. NOT independent-human DX05 review.

This runs on a GitHub-hosted runner separated from the MedPlay worker. Its
GitHub repository and AWS/GCP accounts remain administratively controlled by
one human owner. Successful results have NO native OwnerAct or STOP authority.
"""
import argparse
import copy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sys

REPO="draugustogalvao-pixel/medplay-synthetic-transparency"
REF="refs/heads/main"
WORKFLOW=f"{REPO}/.github/workflows/review-synthetic-governance.yml@{REF}"
CLASS="PUBLIC_SYNTHETIC_ONLY"
MANIFEST_SHA="8d9660f0bdc599e5852dff53fc2df0032c2e9e4f41bc8605fe7696dc07cfddd0"
SAMPLE_SHA="7ccd11385e22b140b25b41e397c8e17b1e07a4c7a2eefc6545b735f9d5531af7"
CLAIMS=["independent_custody_verified","independent_review_verified",
        "distributed_stop_verified","dx05_production_go"]
HEX40=re.compile(r"[0-9a-f]{40}\Z")
INTEGER=re.compile(r"[1-9][0-9]{0,19}\Z")
class Rejected(ValueError):
    pass
def need(cond,code):
    if not cond:
        raise Rejected(code)
def digest(data):
    return hashlib.sha256(data).hexdigest()
def exact_policy():
    return {
      "schema":"MedPlay.R8622PublicSyntheticReviewPolicy/1",
      "policyVersion":"r8622.0",
      "classification":CLASS,
      "reviewMode":"SINGLE_OWNER_AUTOMATED",
      "reviewScope":"SYNTHETIC_SOURCE_REVIEW",
      "allowedRepository":REPO,
      "allowedRef":REF,
      "allowedEvent":"workflow_dispatch",
      "manifestPath":"manifest/synthetic-anchor.json",
      "expectedManifestSha256":MANIFEST_SHA,
      "expectedSampleSha256":SAMPLE_SHA,
      "expectedSampleBytes":56,
      "requiredClaimsFalse":CLAIMS,
      "reviewFindingWhenPassing":"SYNTHETIC_SOURCE_CHECKS_PASS_ONLY",
      "originalDX05StrictModeStillActive":True,
      "ownerScopeApprovedInConversationNotNativeSigned":True,
      "reviewerAdministrativelyIndependent":False,
      "policyActiveInOwnerService":False,
      "mayIssueDX05OwnerAct":False,
      "mayGrantIAM":False,
      "mayStartCloudVM":False,
      "mayAuthorizeClinicalProduction":False,
    }
def policy_check(raw):
    need(isinstance(raw,bytes) and len(raw)<10000,"POLICY_BYTES_INVALID")
    obj=json.loads(raw.decode("utf-8"))
    need(type(obj) is dict and obj==exact_policy(),"POLICY_NOT_APPROVED_FIXED_SYNTHETIC_PROFILE")
    return obj
def manifest_check(raw,policy):
    need(isinstance(raw,bytes) and len(raw)<10000,"MANIFEST_BYTES_INVALID")
    need(digest(raw)==policy["expectedManifestSha256"],"MANIFEST_DIGEST_DRIFT")
    obj=json.loads(raw.decode("utf-8"))
    expected={
      "schema":"MedPlay.PublicSyntheticAnchor/1",
      "classification":CLASS,
      "sample":{
         "kind":"fixed-nonclinical-laboratory-string",
         "sha256":SAMPLE_SHA,
         "size_bytes":56
      },
      "claims":{k:False for k in CLAIMS},
    }
    need(obj==expected,"MANIFEST_CLINICAL_OR_AUTHORITY_DRIFT")
    return obj
def context_check(ctx,policy):
    need(type(ctx) is dict,"RUN_CONTEXT_NOT_OBJECT")
    keys={"GITHUB_REPOSITORY","GITHUB_REF","GITHUB_EVENT_NAME",
          "GITHUB_SHA","GITHUB_RUN_ID","GITHUB_RUN_ATTEMPT",
          "GITHUB_WORKFLOW_REF"}
    need(set(ctx)==keys,"GITHUB_CONTEXT_NOT_EXACT")
    need(ctx["GITHUB_REPOSITORY"]==policy["allowedRepository"],"WRONG_REPOSITORY")
    need(ctx["GITHUB_REF"]==policy["allowedRef"],"WRONG_BRANCH")
    need(ctx["GITHUB_EVENT_NAME"]==policy["allowedEvent"],"UNTRUSTED_TRIGGER")
    need(ctx["GITHUB_WORKFLOW_REF"]==WORKFLOW,"WORKFLOW_IDENTITY_DRIFT")
    need(type(ctx["GITHUB_SHA"]) is str and bool(HEX40.fullmatch(ctx["GITHUB_SHA"])),"GIT_SHA_NOT_PINNED")
    need(type(ctx["GITHUB_RUN_ID"]) is str and bool(INTEGER.fullmatch(ctx["GITHUB_RUN_ID"])),"RUN_ID_INVALID")
    need(ctx["GITHUB_RUN_ATTEMPT"]=="1","RETRY_ATTEMPT_REJECTED")
    return ctx
def build_receipt(policy_bytes,manifest_bytes,env,clock=None):
    policy=policy_check(policy_bytes)
    manifest_check(manifest_bytes,policy)
    context=context_check(env,policy)
    at=clock if clock is not None else datetime.now(timezone.utc)
    need(isinstance(at,datetime) and at.tzinfo is not None,"UTC_TIME_REQUIRED")
    at=at.astimezone(timezone.utc)
    return {
       "schema":"MedPlay.R8622SyntheticReviewReceipt/1",
       "reviewer":"GITHUB_ACTIONS_OIDC_SEPARATE_RUNNER",
       "reviewerAdministrativelyIndependent":False,
       "strictDX05IndependentHumanReviewerSatisfied":False,
       "reviewMode":"SINGLE_OWNER_AUTOMATED",
       "policyActiveInDX05":False,
       "status":"SYNTHETIC_SOURCE_CHECKS_PASS_ONLY",
       "policySha256":digest(policy_bytes),
       "manifestSha256":digest(manifest_bytes),
       "sampleOriginalSha256":SAMPLE_SHA,
       "sampleSizeBytes":56,
       "githubRepository":context["GITHUB_REPOSITORY"],
       "githubRef":context["GITHUB_REF"],
       "githubCommitSha":context["GITHUB_SHA"],
       "githubRunId":context["GITHUB_RUN_ID"],
       "githubRunAttempt":1,
       "githubReviewerWorkflowIdentity":f"https://github.com/{WORKFLOW}",
       "githubOidcCertificateNotYetVerifiedAtReceiptGeneration":True,
       "sourceSyntheticOnly":True,
       "deterministicChecksPassed":True,
       "negativeTestsPassedInWorkflow":True,
       "noPatientData":True,
       "noCloudResourcesCreated":True,
       "reviewTimeUtc":at.isoformat(timespec="seconds"),
       "authorizesOwnerAct":False,
       "authorizesIAM":False,
       "authorizesCloudVM":False,
       "authorizesClinicalProduction":False,
       "independentStopVerified":False,
       "BOOTSTRAP_GO":False,
       "DX_DEV_OPERATIONS_GO":False,
       "GLOBAL_PRODUCTION_GO":False,
    }
def context_from_environment():
    fields=("GITHUB_REPOSITORY","GITHUB_REF","GITHUB_EVENT_NAME","GITHUB_SHA",
            "GITHUB_RUN_ID","GITHUB_RUN_ATTEMPT","GITHUB_WORKFLOW_REF")
    return {k:os.environ.get(k) for k in fields}
def self_test(policy_raw,manifest_raw):
    p=policy_check(policy_raw)
    manifest_check(manifest_raw,p)
    context={
        "GITHUB_REPOSITORY":REPO,"GITHUB_REF":REF,"GITHUB_EVENT_NAME":"workflow_dispatch",
        "GITHUB_SHA":"a"*40,"GITHUB_RUN_ID":"12345","GITHUB_RUN_ATTEMPT":"1",
        "GITHUB_WORKFLOW_REF":WORKFLOW}
    count=0
    good=build_receipt(policy_raw,manifest_raw,context)
    assert good["status"]=="SYNTHETIC_SOURCE_CHECKS_PASS_ONLY";count+=1
    assert good["authorizesOwnerAct"] is False;count+=1
    assert good["authorizesClinicalProduction"] is False;count+=1
    assert good["reviewerAdministrativelyIndependent"] is False;count+=1
    def rejects(f,code=None):
        nonlocal count
        try:f()
        except Rejected as e:
            if code:assert code in str(e),(code,str(e))
        else:raise AssertionError("SHOULD_REJECT")
        count+=1
    for key,value in (
        ("classification","PATIENT_DATA"),("reviewMode","STRICT_INDEPENDENT"),
        ("policyActiveInOwnerService",True),("mayGrantIAM",True),
        ("reviewerAdministrativelyIndependent",True),
        ("originalDX05StrictModeStillActive",False),
        ("mayAuthorizeClinicalProduction",True),
        ("expectedSampleSha256","f"*64)):
        changed=copy.deepcopy(p);changed[key]=value
        rejects(lambda x=changed:policy_check(json.dumps(x).encode()),"POLICY_NOT_APPROVED")
    rejects(lambda:manifest_check(manifest_raw+b"\n",p),"MANIFEST_DIGEST_DRIFT")
    altered=json.loads(manifest_raw)
    altered["claims"]["dx05_production_go"]=True
    rejects(lambda:manifest_check(json.dumps(altered).encode(),p),"MANIFEST_DIGEST_DRIFT")
    for key,value,code in (
        ("GITHUB_REPOSITORY","not-owner/other","WRONG_REPOSITORY"),
        ("GITHUB_REF","refs/heads/test","WRONG_BRANCH"),
        ("GITHUB_EVENT_NAME","pull_request","UNTRUSTED_TRIGGER"),
        ("GITHUB_WORKFLOW_REF","evil/workflow@main","WORKFLOW_IDENTITY_DRIFT"),
        ("GITHUB_SHA","nothex","GIT_SHA_NOT_PINNED"),
        ("GITHUB_RUN_ID","0","RUN_ID_INVALID"),
        ("GITHUB_RUN_ATTEMPT","2","RETRY_ATTEMPT_REJECTED")):
        altered={**context,key:value}
        rejects(lambda x=altered:context_check(x,p),code)
    rejects(lambda:build_receipt(policy_raw,manifest_raw,{**context,"BOOOTSTRAP_GO":True}),"GITHUB_CONTEXT_NOT_EXACT")
    rejects(lambda:build_receipt(policy_raw,manifest_raw,context,datetime(2026,11,9,1)),"UTC_TIME_REQUIRED")
    print("R8622_PUBLIC_SYNTHETIC_NEGATIVE_TESTS_PASS",count)
    return count
def main():
    a=argparse.ArgumentParser()
    a.add_argument("--policy",default="policy/synthetic-review-policy.json")
    a.add_argument("--manifest",default="manifest/synthetic-anchor.json")
    a.add_argument("--output",default="review-receipt.json")
    a.add_argument("--self-test",action="store_true")
    args=a.parse_args()
    raw_policy=Path(args.policy).read_bytes()
    raw_manifest=Path(args.manifest).read_bytes()
    if args.self_test:
        self_test(raw_policy,raw_manifest)
        return
    result=build_receipt(raw_policy,raw_manifest,context_from_environment())
    target=Path(args.output)
    if target.exists():raise Rejected("OUTPUT_ALREADY_EXISTS_NO_RETRY")
    with target.open("x",encoding="utf-8") as f:
        json.dump(result,f,sort_keys=True,indent=2)
        f.write("\n")
    print("R8622_SYNTHETIC_SOURCE_REVIEW_PASS_ONLY")
if __name__=="__main__":
    try:main()
    except (Rejected,ValueError,UnicodeError,KeyError) as err:
        print("R8622_FAIL_CLOSED",type(err).__name__,str(err)[:90],file=sys.stderr)
        raise SystemExit(2)
