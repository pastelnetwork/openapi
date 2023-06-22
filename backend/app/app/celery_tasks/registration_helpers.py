import asyncio
import json
import traceback
from datetime import datetime

from celery import shared_task

from app import crud, schemas
from app.celery_tasks import cascade, sense, nft, collection
from app.celery_tasks.scheduled import logger
from app.core.config import settings
from app.core.status import DbStatus
from app.db.session import db_context
from app.utils import walletnode as wn, pasteld as psl
from app.utils.filestorage import store_file_into_local_cache
from app.utils.ipfs_tools import store_file_to_ipfs


@shared_task(name="registration_helpers:registration_finisher")
def registration_finisher():
    _registration_finisher(
        crud.cascade.get_all_started_not_finished,
        crud.cascade.update,
        crud.cascade.get_by_preburn_txid,
        wn.WalletNodeService.CASCADE,
        "Cascade"
    )
    _registration_finisher(
        crud.sense.get_all_started_not_finished,
        crud.sense.update,
        crud.sense.get_by_preburn_txid,
        wn.WalletNodeService.SENSE,
        "Sense"
    )
    _registration_finisher(
        crud.nft.get_all_started_not_finished,
        crud.nft.update,
        None,
        wn.WalletNodeService.NFT,
        "NFT"
    )
    _registration_finisher(
        crud.collection.get_all_started_not_finished,
        crud.collection.update,
        None,
        wn.WalletNodeService.COLLECTION,
        "Collection"
    )


def _registration_finisher(
        started_not_finished_func,
        update_task_in_db_func,
        get_by_preburn_txid_func,
        wn_service: wn.WalletNodeService,
        service_name):
    logger.info(f"{wn_service} registration_finisher started")
    with db_context() as session:
        # get all tasks with status "STARTED"
        tasks_from_db = started_not_finished_func(session)
    logger.info(f"{wn_service}: Found {len(tasks_from_db)} non finished tasks")
    #
    # TODO: Add finishing logic for tasks stuck with statuses:
    #  "NEW"
    #  "RESTARTED"
    #  "UPLOADED"
    #  "PREBURN_FEE"
    #
    if wn_service == wn.WalletNodeService.CASCADE or wn_service == wn.WalletNodeService.SENSE:
        verb = "action-act"
    elif wn_service == wn.WalletNodeService.NFT:
        verb = "act"
    elif wn_service == wn.WalletNodeService.COLLECTION:
        verb = "collection-act"
    else:
        raise Exception(f"Unknown service {wn_service}")

    for task_from_db in tasks_from_db:
        if task_from_db.wn_task_id:
            try:
                wn_task_status = wn.call(False,
                                         wn_service,
                                         f'{task_from_db.wn_task_id}/history',
                                         {}, [], {}, "", "")
            except Exception as e:
                logger.error(f"Call to WalletNode : {e}")
                wn_task_status = []

            if not wn_task_status:
                # Check using pre-burn txid if somehow reg ticket was registered but WN is not ware of that
                # This can only be used with Sense and Cascade, as NFT does not have burn_txid
                if (wn_service == wn.WalletNodeService.SENSE or wn_service == wn.WalletNodeService.CASCADE) \
                        and task_from_db.burn_txid:
                    reg_ticket = psl.call("tickets", ["find", "action", task_from_db.burn_txid])
                    if reg_ticket and 'txid' in reg_ticket and reg_ticket['txid']:
                        upd = {
                            "reg_ticket_txid": reg_ticket.get("txid"),
                            "status": DbStatus.REGISTERED,
                            "updated_at": datetime.utcnow(),
                        }
                        with db_context() as session:
                            update_task_in_db_func(session, db_obj=task_from_db, obj_in=upd)

                logger.error(f"No result from WalletNode: wn_task_id - {task_from_db.wn_task_id}, "
                             f"ResultId - {task_from_db.result_id}")
                # check how old is the result, if height is more than 48 (2 h), then mark it as ERROR
                height = psl.call("getblockcount", [])
                if height - task_from_db.height > 48:
                    logger.error(f"Task is too old - it was created {height - task_from_db.height} blocks ago:"
                                 f"wn_task_id - {task_from_db.wn_task_id}, ResultId - {task_from_db.result_id}")
                    with db_context() as session:
                        _mark_task_in_db_as_failed(session, task_from_db, update_task_in_db_func,
                                                   get_by_preburn_txid_func, wn_service)
                continue

            add_status_to_history_log(task_from_db, wn_service, wn_task_status)

            logger.debug(f"{wn_service}: Get status from WN. ResultId - {task_from_db.result_id}")

            for step in wn_task_status:
                status = step['status']
                logger.debug(f"{wn_service}: Task status: {status}. ResultId - {task_from_db.result_id}")
                if status == 'Task Rejected':
                    logger.error(f"Task Rejected: wn_task_id - {task_from_db.wn_task_id}, "
                                 f"ResultId - {task_from_db.result_id}")
                    if wn_service != wn.WalletNodeService.NFT and wn_service != wn.WalletNodeService.COLLECTION:
                        if 'details' in step and step['details']:
                            if 'fields' in step['details'] and step['details']['fields']:
                                if 'error_detail' in step['details']['fields'] and step['details']['fields']['error_detail']:
                                    if 'duplicate burnTXID' in step['details']['fields']['error_detail']:
                                        logger.error(f"Task Rejected because of duplicate burnTXID: "
                                                     f"wn_task_id - {task_from_db.wn_task_id}, "
                                                     f"ResultId - {task_from_db.result_id}")
                                        with db_context() as session:
                                            if task_from_db.burn_txid:
                                                crud.preburn_tx.mark_used(session, task_from_db.burn_txid)
                                            cleanup_burn_txid = {"burn_txid": None,}
                                            update_task_in_db_func(session, db_obj=task_from_db, obj_in=cleanup_burn_txid)
                    # mark result as failed, and requires reprocessing
                    with db_context() as session:
                        logger.error(f"{wn_service}: Marking task as ERROR. ResultId - {task_from_db.result_id}")
                        _mark_task_in_db_as_failed(session, task_from_db, update_task_in_db_func,
                                                   get_by_preburn_txid_func, wn_service)
                    break
                if not task_from_db.reg_ticket_txid:
                    reg = status.split(f'Validating {service_name} Reg TXID: ', 1)
                    if len(reg) != 2:
                        reg = status.split(f'Validated {service_name} Reg TXID: ', 1)
                    if len(reg) == 2:
                        logger.info(f"{wn_service}: Found reg ticket txid: {reg[1]}. ResultId - {task_from_db.result_id}")
                        upd = {"reg_ticket_txid": reg[1], "updated_at": datetime.utcnow()}
                        with db_context() as session:
                            update_task_in_db_func(session, db_obj=task_from_db, obj_in=upd)
                        continue
                if not task_from_db.act_ticket_txid:
                    if task_from_db.reg_ticket_txid:
                        act_ticket = psl.call("tickets", ['find', verb, task_from_db.reg_ticket_txid])
                        if act_ticket and 'txid' in act_ticket and act_ticket['txid']:
                            logger.info(f"{wn_service}: Found act ticket txid from Pastel network: {act_ticket['txid']}."
                                        f" ResultId - {task_from_db.result_id}")
                            _finalize_registration(task_from_db, act_ticket['txid'], update_task_in_db_func, wn_service)
                            break
                    act = status.split(f'Activated {service_name} Registration Ticket TXID: ', 1)
                    if len(act) == 2:
                        logger.info(f"{wn_service}: Found act ticket txid from WalletNode: {act[2]}."
                                        f" ResultId - {task_from_db.result_id}")
                        _finalize_registration(task_from_db, act[2], update_task_in_db_func, wn_service)
                        break


def add_status_to_history_log(task_from_db, wn_service, wn_task_status):
    if wn_task_status:
        with db_context() as session:
            if wn_service == wn.WalletNodeService.CASCADE:
                log = schemas.CascadeHistoryLog(
                    wn_file_id=task_from_db.wn_file_id,
                    wn_task_id=task_from_db.wn_task_id,
                    task_status=task_from_db.process_status,
                    status_messages=str(wn_task_status),
                    retry_count=task_from_db.retry_num,
                    pastel_id=task_from_db.pastel_id,
                    cascade_task_id=task_from_db.id,
                )
                crud.cascade_log.create(session, obj_in=log)
            elif wn_service == wn.WalletNodeService.SENSE:
                log = schemas.SenseHistoryLog(
                    wn_file_id=task_from_db.wn_file_id,
                    wn_task_id=task_from_db.wn_task_id,
                    task_status=task_from_db.process_status,
                    status_messages=str(wn_task_status),
                    retry_count=task_from_db.retry_num,
                    pastel_id=task_from_db.pastel_id,
                    sense_task_id=task_from_db.id,
                )
                crud.sense_log.create(session, obj_in=log)
            elif wn_service == wn.WalletNodeService.NFT:
                log = schemas.NftHistoryLog(
                    wn_file_id=task_from_db.wn_file_id,
                    wn_task_id=task_from_db.wn_task_id,
                    task_status=task_from_db.process_status,
                    status_messages=str(wn_task_status),
                    retry_count=task_from_db.retry_num,
                    pastel_id=task_from_db.pastel_id,
                    nft_task_id=task_from_db.id,
                )
                crud.nft_log.create(session, obj_in=log)


def _finalize_registration(task_from_db, act_txid, update_task_in_db_func, wn_service: wn.WalletNodeService):
    logger.debug(f"{wn_service}: Finalizing registration: {task_from_db.id}")

    if wn_service == wn.WalletNodeService.COLLECTION:
        upd = {
            "act_ticket_txid": act_txid,
            "process_status": DbStatus.DONE.value,
            "updated_at": datetime.utcnow()
        }
        with db_context() as session:
            update_task_in_db_func(session, db_obj=task_from_db, obj_in=upd)
        return

    stored_file_ipfs_link = task_from_db.stored_file_ipfs_link
    if wn_service == wn.WalletNodeService.NFT:
        nft_dd_file_ipfs_link = task_from_db.nft_dd_file_ipfs_link
    try:
        logger.debug(f"{wn_service}: Downloading registered file from Pastel: {task_from_db.reg_ticket_txid}")
        file_bytes = asyncio.run(wn.get_file_from_pastel(reg_ticket_txid=task_from_db.reg_ticket_txid,
                                                         wn_service=wn_service))
        if file_bytes:
            logger.debug(f"{wn_service}: Storing downloaded file into local cache: {task_from_db.reg_ticket_txid}")
            cached_result_file = asyncio.run(store_file_into_local_cache(
                reg_ticket_txid=task_from_db.reg_ticket_txid,
                file_bytes=file_bytes))
            if not task_from_db.stored_file_ipfs_link:
                logger.debug(f"{wn_service}: Storing downloaded file into IPFS cache: {task_from_db.reg_ticket_txid}")
                # store_file_into_local_cache throws exception, so if we are here, file is in local cache
                stored_file_ipfs_link = asyncio.run(store_file_to_ipfs(cached_result_file))

        if wn_service == wn.WalletNodeService.NFT:
            logger.debug(f"{wn_service}: Requesting NFT sense data from WN: {task_from_db.reg_ticket_txid}")
            dd_data = asyncio.run(wn.get_nft_dd_result_from_pastel(reg_ticket_txid=task_from_db.reg_ticket_txid))
            if dd_data:
                if isinstance(dd_data, dict):
                    dd_bytes = json.dumps(dd_data).encode('utf-8')
                else:
                    dd_bytes = dd_data.encode('utf-8')
                logger.debug(f"{wn_service}: Storing NFT sense data to local cache: {task_from_db.reg_ticket_txid}")
                cached_dd_file = asyncio.run(store_file_into_local_cache(
                    reg_ticket_txid=task_from_db.reg_ticket_txid,
                    file_bytes=dd_bytes,
                    extra_suffix=".dd"))
                if not task_from_db.nft_dd_file_ipfs_link:
                    # store_file_into_local_cache throws exception, so if we are here, file is in local cache
                    logger.debug(f"{wn_service}: Storing NFT sense data to IPFS: {task_from_db.reg_ticket_txid}")
                    nft_dd_file_ipfs_link = asyncio.run(store_file_to_ipfs(cached_dd_file))

    except Exception as e:
        logger.error(f"{wn_service}: Failed to get file from Pastel: {e}")

    upd = {
        "act_ticket_txid": act_txid,
        "process_status": DbStatus.DONE.value,
        "stored_file_ipfs_link": stored_file_ipfs_link,
        "updated_at": datetime.utcnow()
    }
    if wn_service == wn.WalletNodeService.NFT:
        upd["nft_dd_file_ipfs_link"] = nft_dd_file_ipfs_link

    with db_context() as session:
        logger.debug(f"{wn_service}: Updating task in DB as DONE: {task_from_db.reg_ticket_txid}")
        update_task_in_db_func(session, db_obj=task_from_db, obj_in=upd)
        if wn_service != wn.WalletNodeService.NFT:      # check for wn.WalletNodeService.COLLECTION was before
            crud.preburn_tx.mark_used(session, task_from_db.burn_txid)

        # Now when all is finalized, see if we need to transfer the ticket to another PastelID
        if wn_service == wn.WalletNodeService.CASCADE or wn_service == wn.WalletNodeService.NFT:
            if task_from_db.offer_ticket_intended_rcpt_pastel_id:
                pastel_id = task_from_db.offer_ticket_intended_rcpt_pastel_id
                logger.debug(f"{wn_service}: This ticket {task_from_db.reg_ticket_txid} "
                             f"has to transferred to another PastelID: {task_from_db.offer_ticket_intended_rcpt_pastel_id}")
                # check this just for sanity, should not happen!
                if task_from_db.offer_ticket_txid:
                    logger.warn(f"{wn_service}: Offer ticket already exists!: {task_from_db.offer_ticket_txid}")
                    return
                offer_ticket = asyncio.run(psl.create_offer_ticket(task_from_db, pastel_id))
                if offer_ticket and 'txid' in offer_ticket and offer_ticket['txid']:
                    logger.debug(f"{wn_service}: Updating task in DB as offered to transfer: {task_from_db.reg_ticket_txid}")
                    upd = {"offer_ticket_txid": offer_ticket['txid'],
                           "offer_ticket_intended_rcpt_pastel_id": pastel_id,
                           "updated_at": datetime.utcnow()}
                    update_task_in_db_func(session, db_obj=task_from_db, obj_in=upd)


def _mark_task_in_db_as_failed(session,
                               task_from_db,
                               update_task_in_db_func,
                               get_by_preburn_txid_func,
                               wn_service: wn.WalletNodeService):
    logger.info(f"Marking task as failed: {task_from_db.id}")
    upd = {"process_status": DbStatus.ERROR.value, "updated_at": datetime.utcnow()}
    update_task_in_db_func(session, db_obj=task_from_db, obj_in=upd)
    if wn_service != wn.WalletNodeService.NFT and wn_service != wn.WalletNodeService.COLLECTION\
            and get_by_preburn_txid_func:
        t = get_by_preburn_txid_func(session, txid=task_from_db.burn_txid)
        if not t:
            crud.preburn_tx.mark_non_used(session, task_from_db.burn_txid)
    logger.error(f"Result {task_from_db.result_id} failed")


@shared_task(name="registration_helpers:registration_re_processor")
def registration_re_processor():

    _registration_re_processor(
        crud.cascade.get_all_failed,
        crud.cascade.update,
        _start_reprocess_cascade,
        wn.WalletNodeService.CASCADE,
    )
    _registration_re_processor(
        crud.sense.get_all_failed,
        crud.sense.update,
        _start_reprocess_sense,
        wn.WalletNodeService.SENSE,
    )
    _registration_re_processor(
        crud.nft.get_all_failed,
        crud.nft.update,
        _start_reprocess_nft,
        wn.WalletNodeService.NFT,
    )
    _registration_re_processor(
        crud.collection.get_all_failed,
        crud.collection.update,
        _start_reprocess_collection,
        wn.WalletNodeService.COLLECTION,
    )


def _registration_re_processor(all_failed_func, update_task_in_db_func, reprocess_func,
                               wn_service: wn.WalletNodeService):
    logger.info(f"{wn_service} registration_re_processor started")
    with db_context() as session:
        tasks_from_db = all_failed_func(session)
    logger.info(f"{wn_service}: Found {len(tasks_from_db)} failed tasks")
    for task_from_db in tasks_from_db:
        try:
            # get interval from previous update
            # if that interval less than reprocess interval multiplied by number of retries, skip
            interval = datetime.utcnow() - task_from_db.updated_at
            if interval.seconds < settings.REGISTRATION_RE_PROCESSOR_INTERVAL * task_from_db.retry_num:
                logger.debug(f"Task {task_from_db.id} was reprocessed recently, skipping: time from last update: "
                             f"{interval.seconds} seconds; wait time for the next reprocess after previous: "
                             f"{settings.REGISTRATION_RE_PROCESSOR_INTERVAL * task_from_db.retry_num} seconds "
                             f"(this is retry number {task_from_db.retry_num}); next re-process in "
                             f"{settings.REGISTRATION_RE_PROCESSOR_INTERVAL * task_from_db.retry_num - interval.seconds} "
                             f"seconds")
                continue

            if not task_from_db.process_status or task_from_db.process_status == "":
                logger.debug(f"Task status is empty, check if other data is empty too: {task_from_db.result_id}")
                if (not task_from_db.reg_ticket_txid and not task_from_db.act_ticket_txid) \
                        or not task_from_db.pastel_id or not task_from_db.wn_task_id\
                        or (wn_service != wn.WalletNodeService.NFT and not task_from_db.burn_txid) \
                        or not task_from_db.wn_file_id:
                    logger.debug(f"Task status is empty, clearing and reprocessing: {task_from_db.result_id}")
                    _clear_task_in_db(task_from_db, update_task_in_db_func, wn_service)
                    # clear_task_in_db sets task's status to RESTARTED
                    reprocess_func(task_from_db)
                    continue
                else:
                    logger.debug(f"Task status is empty, but other data is not empty, "
                                 f"marking as {DbStatus.STARTED.value}: {task_from_db.id}")
                    upd = {"process_status": DbStatus.STARTED.value, "updated_at": datetime.utcnow()}
                    with db_context() as session:
                        update_task_in_db_func(session, db_obj=task_from_db, obj_in=upd)

            if task_from_db.process_status == DbStatus.ERROR.value:
                if task_from_db.reg_ticket_txid or task_from_db.act_ticket_txid:
                    logger.debug(f"Task status is {DbStatus.ERROR.value}, "
                                 f"but reg_ticket_txid [{task_from_db.reg_ticket_txid}] or "
                                 f"act_ticket_txid is not empty [{task_from_db.act_ticket_txid}], "
                                 f"marking as {DbStatus.REGISTERED.value}: {task_from_db.result_id}")
                    upd = {"process_status": DbStatus.REGISTERED.value, "updated_at": datetime.utcnow()}
                    with db_context() as session:
                        update_task_in_db_func(session, db_obj=task_from_db, obj_in=upd)
                    continue
                logger.debug(f"Task status is {DbStatus.ERROR.value}, "
                             f"clearing and reprocessing: {task_from_db.result_id}")
                _clear_task_in_db(task_from_db, update_task_in_db_func, wn_service)
                # clear_task_in_db sets task's status to RESTARTED
                reprocess_func(task_from_db)
        except Exception as e:
            traceback.print_exc()
            logger.error(f"Registration reprocessing failed for ticket {task_from_db.result_id} with error {e}")
            continue


def _clear_task_in_db(task_from_db, update_task_in_db_func, wn_service: wn.WalletNodeService):
    logger.info(f"Clearing task: {task_from_db.result_id}")
    if task_from_db.retry_num:
        retries = task_from_db.retry_num + 1
    else:
        retries = 1
    cleanup = {
        "wn_task_id": None,
        "pastel_id": None,
        "reg_ticket_txid": None,
        "act_ticket_txid": None,
        "process_status": DbStatus.RESTARTED.value,
        "retry_num": retries,
        "updated_at": datetime.utcnow()
    }
    if wn_service != wn.WalletNodeService.COLLECTION:
        cleanup["wn_file_id"] = None
        cleanup["wn_fee"] = None

    with db_context() as session:
        if wn_service != wn.WalletNodeService.NFT and wn_service != wn.WalletNodeService.COLLECTION:
            cleanup["burn_txid"] = None
            if task_from_db.burn_txid:
                crud.preburn_tx.mark_non_used(session, task_from_db.burn_txid)
        update_task_in_db_func(session, db_obj=task_from_db, obj_in=cleanup)


def _start_reprocess_cascade(task_from_db):
    logger.debug(f"Restarting Cascade registration for result {task_from_db.result_id}...")
    res = (
            cascade.re_register_file.s(task_from_db.result_id) |
            cascade.preburn_fee.s() |
            cascade.process.s()
    ).apply_async()
    logger.info(f"Cascade Registration restarted for result {task_from_db.result_id} with task id {res.task_id}")


def _start_reprocess_sense(task_from_db):
    logger.debug(f"Restarting Sense registration for result {task_from_db.result_id}...")
    res = (
            sense.re_register_file.s(task_from_db.result_id) |
            sense.preburn_fee.s() |
            sense.process.s()
    ).apply_async()
    logger.info(f"Sense Registration restarted for result {task_from_db.result_id} with task id {res.task_id}")


def _start_reprocess_nft(task_from_db):
    logger.debug(f"Restarting NFT registration for result {task_from_db.result_id}...")
    res = (
            nft.re_register_file.s(task_from_db.result_id) |
            nft.process.s()
    ).apply_async()
    logger.info(f"NFT Registration restarted for result {task_from_db.result_id} with task id {res.task_id}")


def _start_reprocess_collection(task_from_db):
    logger.debug(f"Restarting Collection registration for result {task_from_db.result_id}...")
    res = (
            collection.process.s(task_from_db.result_id)
    ).apply_async()
    logger.info(f"NFT Registration restarted for result {task_from_db.result_id} with task id {res.task_id}")