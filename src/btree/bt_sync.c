/*-
 * Copyright (c) 2008-2014 WiredTiger, Inc.
 *	All rights reserved.
 *
 * See the file LICENSE for redistribution information.
 */

#include "wt_internal.h"

/*
 * __wt_bt_cache_force_write --
 *	Dirty the root page of the tree so it gets written.
 */
int
__wt_bt_cache_force_write(WT_SESSION_IMPL *session)
{
	WT_BTREE *btree;
	WT_PAGE *page;

	btree = S2BT(session);
	page = btree->root.page;

	/* Dirty the root page to ensure a write. */
	WT_RET(__wt_page_modify_init(session, page));
	__wt_page_modify_set(session, page);

	return (0);
}

/*
 * __wt_bt_cache_op --
 *	Cache operations.
 */
int
__wt_bt_cache_op(WT_SESSION_IMPL *session, WT_CKPT *ckptbase, int op)
{
	WT_DECL_RET;
	WT_BTREE *btree;

	btree = S2BT(session);

	switch (op) {
	case WT_SYNC_CHECKPOINT:
	case WT_SYNC_DISCARD:
		/*
		 * XXX
		 * Set the checkpoint reference for reconciliation -- this is
		 * ugly, but there's no data structure path from here to the
		 * reconciliation of the tree's root page.
		 */
		WT_ASSERT(session, btree->ckpt == NULL);
		btree->ckpt = ckptbase;
		break;
	}

	switch (op) {
	case WT_SYNC_CHECKPOINT:
	case WT_SYNC_WRITE_LEAVES:
		WT_ERR(__wt_sync_file(session, op));
		break;
	case WT_SYNC_DISCARD:
	case WT_SYNC_DISCARD_NOWRITE:
		WT_ERR(__wt_evict_file(session, op));
		break;
	WT_ILLEGAL_VALUE_ERR(session);
	}

err:	switch (op) {
	case WT_SYNC_CHECKPOINT:
	case WT_SYNC_DISCARD:
		btree->ckpt = NULL;
		break;
	}

	return (ret);
}
