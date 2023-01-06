import asyncio

from fastapi import APIRouter, Depends, HTTPException, UploadFile, WebSocket, Query

from typing import List
from sqlalchemy.orm import Session

import app.celery_tasks.cascade as cascade
import app.db.session as session
from app.api import deps, common
from app import models, crud, schemas
import app.utils.walletnode as wn


router = APIRouter()


@router.post("/", response_model=schemas.WorkResult, response_model_exclude_none=True)
async def do_work(
        *,
        files: List[UploadFile],
        db: Session = Depends(session.get_db_session),
        api_key: models.ApiKey = Depends(deps.APIKeyAuth.get_api_key_for_cascade),
        current_user: models.User = Depends(deps.APIKeyAuth.get_user_by_apikey)
) -> schemas.WorkResult:
    return await common.do_works(worker=cascade, files=files, user_id=current_user.id)


@router.get("/works", response_model=List[schemas.WorkResult], response_model_exclude_none=True)
async def get_works(
        *,
        db: Session = Depends(session.get_db_session),
        api_key: models.ApiKey = Depends(deps.APIKeyAuth.get_api_key_for_cascade),
        current_user: models.User = Depends(deps.APIKeyAuth.get_user_by_apikey)
) -> List[schemas.WorkResult]:
    """
    Return the status of the submitted Work
    """
    tickets = crud.cascade.get_multi_by_owner(db=db, owner_id=current_user.id)
    if not tickets:
        raise HTTPException(status_code=404, detail="No works found")
    return await common.parse_users_works(tickets, wn.WalletNodeService.CASCADE)


@router.get("/works/{work_id}", response_model=schemas.WorkResult, response_model_exclude_none=True)
async def get_work(
        *,
        work_id: str,
        db: Session = Depends(session.get_db_session),
        api_key: models.ApiKey = Depends(deps.APIKeyAuth.get_api_key_for_cascade),
        current_user: models.User = Depends(deps.APIKeyAuth.get_user_by_apikey)
) -> schemas.WorkResult:
    """
    Return the status of the submitted Work
    """
    tickets_in_work = crud.cascade.get_all_in_work(db=db, work_id=work_id, owner_id=current_user.id)
    if not tickets_in_work:
        raise HTTPException(status_code=404, detail="No tickets or work found")
    return await common.parse_user_work(tickets_in_work, work_id, wn.WalletNodeService.CASCADE)


@router.get("/tickets", response_model=List[schemas.TicketRegistrationResult], response_model_exclude_none=True)
async def get_tickets(
        *,
        db: Session = Depends(session.get_db_session),
        api_key: models.ApiKey = Depends(deps.APIKeyAuth.get_api_key_for_cascade),
        current_user: models.User = Depends(deps.APIKeyAuth.get_user_by_apikey)
) -> List[schemas.TicketRegistrationResult]:
    results = []
    tickets = crud.cascade.get_multi_by_owner(db=db, owner_id=current_user.id)
    if not tickets:
        raise HTTPException(status_code=404, detail="No works found")
    for ticket in tickets:
        ticket_result = await common.check_ticket_registration_status(ticket, wn.WalletNodeService.CASCADE)
        results.append(ticket_result)
    return results


@router.get("/tickets/{ticket_id}", response_model=schemas.TicketRegistrationResult, response_model_exclude_none=True)
async def get_ticket(
        *,
        ticket_id: str,
        db: Session = Depends(session.get_db_session),
        api_key: models.ApiKey = Depends(deps.APIKeyAuth.get_api_key_for_cascade),
        current_user: models.User = Depends(deps.APIKeyAuth.get_user_by_apikey)
) -> schemas.TicketRegistrationResult:
    ticket = crud.cascade.get_by_ticket_id_and_owner(db=db, ticket_id=ticket_id, owner_id=current_user.id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return await common.check_ticket_registration_status(ticket, wn.WalletNodeService.CASCADE)


@router.get("/file/{ticket_id}")
async def get_file(
        *,
        ticket_id: str,
        db: Session = Depends(session.get_db_session),
        api_key: models.ApiKey = Depends(deps.APIKeyAuth.get_api_key_for_cascade),
        current_user: models.User = Depends(deps.APIKeyAuth.get_user_by_apikey)
):
    ticket = crud.cascade.get_by_ticket_id_and_owner(db=db, ticket_id=ticket_id, owner_id=current_user.id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return await common.get_file(ticket=ticket, service=wn.WalletNodeService.CASCADE)


@router.get("/data/regtxid/{txid_id}")
async def get_data_by_reg_txid(
        *,
        txid_id: str,
        db: Session = Depends(session.get_db_session),
        api_key: models.ApiKey = Depends(deps.APIKeyAuth.get_api_key_for_sense),
        current_user: models.User = Depends(deps.APIKeyAuth.get_user_by_apikey)
):
    ticket = crud.cascade.get_by_reg_txid_and_owner(db=db, owner_id=current_user.id, reg_txid=txid_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return await common.get_file(ticket=ticket, service=wn.WalletNodeService.CASCADE)


@router.get("/data/acttxid/{txid_id}")
async def get_data_by_reg_txid(
        *,
        txid_id: str,
        db: Session = Depends(session.get_db_session),
        api_key: models.ApiKey = Depends(deps.APIKeyAuth.get_api_key_for_sense),
        current_user: models.User = Depends(deps.APIKeyAuth.get_user_by_apikey)
):
    ticket = crud.cascade.get_by_act_txid_and_owner(db=db, owner_id=current_user.id, act_txid=txid_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return await common.get_file(ticket=ticket, service=wn.WalletNodeService.CASCADE)


@router.websocket("/status/work")
async def work_status(
        websocket: WebSocket,
        api_key: str = Query(default=None),
        db: Session = Depends(session.get_db_session),
):
    await websocket.accept()

    apikey = await deps.APIKeyAuth.get_api_key_for_cascade(db, api_key)

    while True:
        data = await websocket.receive_text()
        await websocket.send_text(f"Message received: {data}")


@router.websocket("/status/ticket")
async def ticket_status(
        websocket: WebSocket,
        ticket_id: str = Query(default=None),
        api_key: str = Query(default=None),
        db: Session = Depends(session.get_db_session),
):
    await websocket.accept()

    await deps.APIKeyAuth.get_api_key_for_cascade(db, api_key)
    current_user = await deps.APIKeyAuth.get_user_by_apikey(db, api_key)

    ticket = crud.cascade.get_by_ticket_id_and_owner(db=db, ticket_id=ticket_id, owner_id=current_user.id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    while True:
        result = await common.check_ticket_registration_status(ticket, wn.WalletNodeService.CASCADE)
        if result is not None:
            await websocket.send_text(f"Ticket {result.ticket_id} status: {result.status}")
        await asyncio.sleep(150)    # 2.5 minutes
