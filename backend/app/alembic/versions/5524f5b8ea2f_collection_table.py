"""Collection table

Revision ID: 5524f5b8ea2f
Revises: 9d8e7e8cc856
Create Date: 2023-06-19 20:42:14.715927

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '5524f5b8ea2f'
down_revision = '9d8e7e8cc856'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('collection',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('result_id', sa.String(), nullable=True),
    sa.Column('item_type', sa.String(), nullable=True),
    sa.Column('pastel_id', sa.String(), nullable=True),
    sa.Column('collection_name', sa.String(), nullable=True),
    sa.Column('max_collection_entries', sa.Integer(), nullable=True),
    sa.Column('collection_item_copy_count', sa.Integer(), nullable=True),
    sa.Column('authorized_pastel_ids', sa.ARRAY(sa.String()), nullable=True),
    sa.Column('max_permitted_open_nsfw_score', sa.Float(), nullable=True),
    sa.Column('minimum_similarity_score_to_first_entry_in_collection', sa.Float(), nullable=True),
    sa.Column('no_of_days_to_finalize_collection', sa.Integer(), nullable=True),
    sa.Column('royalty', sa.Float(), nullable=True),
    sa.Column('green', sa.Boolean(), nullable=True),
    sa.Column('height', sa.Integer(), nullable=True),
    sa.Column('process_status', sa.String(), nullable=True),
    sa.Column('spendable_address', sa.String(), nullable=True),
    sa.Column('retry_num', sa.Integer(), nullable=True),
    sa.Column('wn_task_id', sa.String(), nullable=True),
    sa.Column('reg_ticket_txid', sa.String(), nullable=True),
    sa.Column('act_ticket_txid', sa.String(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.Column('owner_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['owner_id'], ['user.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_collection_act_ticket_txid'), 'collection', ['act_ticket_txid'], unique=False)
    op.create_index(op.f('ix_collection_authorized_pastel_ids'), 'collection', ['authorized_pastel_ids'], unique=False)
    op.create_index(op.f('ix_collection_collection_item_copy_count'), 'collection', ['collection_item_copy_count'], unique=False)
    op.create_index(op.f('ix_collection_collection_name'), 'collection', ['collection_name'], unique=False)
    op.create_index(op.f('ix_collection_height'), 'collection', ['height'], unique=False)
    op.create_index(op.f('ix_collection_id'), 'collection', ['id'], unique=False)
    op.create_index(op.f('ix_collection_item_type'), 'collection', ['item_type'], unique=False)
    op.create_index(op.f('ix_collection_max_collection_entries'), 'collection', ['max_collection_entries'], unique=False)
    op.create_index(op.f('ix_collection_max_permitted_open_nsfw_score'), 'collection', ['max_permitted_open_nsfw_score'], unique=False)
    op.create_index(op.f('ix_collection_minimum_similarity_score_to_first_entry_in_collection'), 'collection', ['minimum_similarity_score_to_first_entry_in_collection'], unique=False)
    op.create_index(op.f('ix_collection_no_of_days_to_finalize_collection'), 'collection', ['no_of_days_to_finalize_collection'], unique=False)
    op.create_index(op.f('ix_collection_pastel_id'), 'collection', ['pastel_id'], unique=False)
    op.create_index(op.f('ix_collection_reg_ticket_txid'), 'collection', ['reg_ticket_txid'], unique=False)
    op.create_index(op.f('ix_collection_result_id'), 'collection', ['result_id'], unique=False)
    op.create_index(op.f('ix_collection_process_status'), 'collection', ['process_status'], unique=False)
    op.create_index(op.f('ix_collection_royalty'), 'collection', ['royalty'], unique=False)
    op.create_index(op.f('ix_collection_spendable_address'), 'collection', ['spendable_address'], unique=False)
    op.create_index(op.f('ix_collection_wn_task_id'), 'collection', ['wn_task_id'], unique=False)
    op.create_table('collectionhistory',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('wn_file_id', sa.String(), nullable=True),
    sa.Column('wn_task_id', sa.String(), nullable=True),
    sa.Column('task_status', sa.String(), nullable=True),
    sa.Column('status_messages', sa.String(), nullable=True),
    sa.Column('retry_number', sa.Integer(), nullable=True),
    sa.Column('pastel_id', sa.String(), nullable=True),
    sa.Column('collection_task_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['collection_task_id'], ['collection.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_collectionhistory_id'), 'collectionhistory', ['id'], unique=False)
    op.create_index(op.f('ix_collectionhistory_pastel_id'), 'collectionhistory', ['pastel_id'], unique=False)
    op.create_index(op.f('ix_collectionhistory_wn_file_id'), 'collectionhistory', ['wn_file_id'], unique=False)
    op.create_index(op.f('ix_collectionhistory_wn_task_id'), 'collectionhistory', ['wn_task_id'], unique=False)
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index(op.f('ix_collectionhistory_wn_task_id'), table_name='collectionhistory')
    op.drop_index(op.f('ix_collectionhistory_wn_file_id'), table_name='collectionhistory')
    op.drop_index(op.f('ix_collectionhistory_pastel_id'), table_name='collectionhistory')
    op.drop_index(op.f('ix_collectionhistory_id'), table_name='collectionhistory')
    op.drop_table('collectionhistory')
    op.drop_index(op.f('ix_collection_wn_task_id'), table_name='collection')
    op.drop_index(op.f('ix_collection_spendable_address'), table_name='collection')
    op.drop_index(op.f('ix_collection_royalty'), table_name='collection')
    op.drop_index(op.f('ix_collection_process_status'), table_name='collection')
    op.drop_index(op.f('ix_collection_result_id'), table_name='collection')
    op.drop_index(op.f('ix_collection_reg_ticket_txid'), table_name='collection')
    op.drop_index(op.f('ix_collection_pastel_id'), table_name='collection')
    op.drop_index(op.f('ix_collection_no_of_days_to_finalize_collection'), table_name='collection')
    op.drop_index(op.f('ix_collection_minimum_similarity_score_to_first_entry_in_collection'), table_name='collection')
    op.drop_index(op.f('ix_collection_max_permitted_open_nsfw_score'), table_name='collection')
    op.drop_index(op.f('ix_collection_max_collection_entries'), table_name='collection')
    op.drop_index(op.f('ix_collection_item_type'), table_name='collection')
    op.drop_index(op.f('ix_collection_id'), table_name='collection')
    op.drop_index(op.f('ix_collection_height'), table_name='collection')
    op.drop_index(op.f('ix_collection_collection_name'), table_name='collection')
    op.drop_index(op.f('ix_collection_collection_item_copy_count'), table_name='collection')
    op.drop_index(op.f('ix_collection_authorized_pastel_ids'), table_name='collection')
    op.drop_index(op.f('ix_collection_act_ticket_txid'), table_name='collection')
    op.drop_table('collection')
    # ### end Alembic commands ###
