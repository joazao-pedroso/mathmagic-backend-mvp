"""Adiciona a coluna sala_id na tabela aluno

Revision ID: e5aafb8fd65c
Revises: 
Create Date: 2025-09-19 14:59:53.915420

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e5aafb8fd65c'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # ### Início dos comandos para a migração um-para-muitos ###

    # 1. Apaga as restrições de chaves estrangeiras da tabela intermediária 'aluno_sala'
    op.drop_constraint('fk_aluno_sala_aluno', 'aluno_sala', type_='foreignkey')
    op.drop_constraint('fk_aluno_sala_sala', 'aluno_sala', type_='foreignkey')

    # 2. Apaga a tabela intermediária 'aluno_sala' que criava a relação muitos-para-muitos
    op.drop_table('aluno_sala')

    # 3. Adiciona a nova coluna 'sala_id' na tabela 'aluno'
    with op.batch_alter_table('aluno', schema=None) as batch_op:
        batch_op.add_column(sa.Column('sala_id', sa.Integer(), nullable=False))
        batch_op.create_foreign_key('fk_aluno_sala', 'aluno', ['sala_id'], ['id'])

    # ### Fim dos comandos ###


def downgrade():
    # ### Início dos comandos para reverter a migração ###

    # 1. Apaga a chave estrangeira e a coluna 'sala_id' da tabela 'aluno'
    with op.batch_alter_table('aluno', schema=None) as batch_op:
        batch_op.drop_constraint('fk_aluno_sala', type_='foreignkey')
        batch_op.drop_column('sala_id')

    # 2. Recria a tabela intermediária 'aluno_sala'
    op.create_table('aluno_sala',
        sa.Column('aluno_id', sa.Integer(), nullable=False),
        sa.Column('sala_id', sa.Integer(), nullable=False)
    )

    # 3. Adiciona as chaves estrangeiras da tabela intermediária
    op.create_foreign_key('fk_aluno_sala_aluno', 'aluno_sala', 'aluno', ['aluno_id'], ['id'])
    op.create_foreign_key('fk_aluno_sala_sala', 'aluno_sala', 'sala', ['sala_id'], ['id'])

    # ### Fim dos comandos ###