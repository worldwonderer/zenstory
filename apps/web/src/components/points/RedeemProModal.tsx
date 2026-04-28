/**
 * Redeem Pro Modal Component - Modal for redeeming points for Pro subscription
 */
import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { pointsApi } from '../../lib/pointsApi';
import { useTranslation } from 'react-i18next';
import Modal from '../ui/Modal';

interface RedeemProModalProps {
  isOpen: boolean;
  onClose: () => void;
}

const REDEEM_OPTIONS = [
  { days: 7, cost: 100 },
  { days: 14, cost: 200 },
  { days: 30, cost: 400 },
];

export function RedeemProModal({ isOpen, onClose }: RedeemProModalProps) {
  const { t } = useTranslation(['points', 'common']);
  const [selectedDays, setSelectedDays] = useState(7);
  const queryClient = useQueryClient();

  const { data: balanceData } = useQuery({
    queryKey: ['points-balance'],
    queryFn: () => pointsApi.getBalance(),
    enabled: isOpen,
  });

  const balance = balanceData?.available ?? 0;

  const redeemMutation = useMutation({
    mutationFn: (days: number) => pointsApi.redeemForPro(days),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['points-balance'] });
      queryClient.invalidateQueries({ queryKey: ['subscription-status'] });
      queryClient.invalidateQueries({ queryKey: ['subscription-quota'] });
      queryClient.invalidateQueries({ queryKey: ['subscription'] });
      queryClient.invalidateQueries({ queryKey: ['quota'] });
      onClose();
    },
  });

  const handleRedeem = () => {
    redeemMutation.mutate(selectedDays);
  };

  const selectedOption = REDEEM_OPTIONS.find(o => o.days === selectedDays);
  const canAfford = selectedOption ? balance >= selectedOption.cost : false;

  const footer = (
    <>
      <button
        onClick={onClose}
        className="flex-1 px-4 py-2 text-sm font-medium text-[hsl(var(--text-secondary))] bg-[hsl(var(--bg-tertiary))] rounded-lg hover:bg-[hsl(var(--bg-hover))] transition-colors"
      >
        {t('common:cancel', '取消')}
      </button>
      <button
        onClick={handleRedeem}
        disabled={!canAfford || redeemMutation.isPending}
        className="flex-1 px-4 py-2 text-sm font-medium text-white bg-gradient-to-r from-purple-500 to-blue-500 rounded-lg hover:from-purple-600 hover:to-blue-600 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
      >
        {redeemMutation.isPending
          ? t('common:processing', '处理中...')
          : canAfford
          ? t('redeem', '兑换')
          : t('insufficient', '积分不足')}
      </button>
    </>
  );

  return (
    <Modal
      open={isOpen}
      onClose={onClose}
      title={t('redeemPro', '兑换 Pro 会员')}
      footer={footer}
      size="md"
    >
      {/* Current Balance */}
      <div className="mb-4 p-3 bg-[hsl(var(--warning)/0.1)] rounded-lg">
        <div className="flex items-center gap-2">
          <svg className="w-5 h-5 text-[hsl(var(--warning))]" fill="currentColor" viewBox="0 0 20 20">
            <path d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.736 6.979C9.208 6.193 9.696 6 10 6c.304 0 .792.193 1.264.979a1 1 0 001.715-1.029C12.279 4.784 11.232 4 10 4s-2.279.784-2.979 1.95c-.285.475-.507 1-.67 1.55H6a1 1 0 000 2h.013a9.358 9.358 0 000 1H6a1 1 0 100 2h.351c.163.55.385 1.075.67 1.55C7.721 15.216 8.768 16 10 16s2.279-.784 2.979-1.95a1 1 0 10-1.715-1.029c-.472.786-.96.979-1.264.979-.304 0-.792-.193-1.264-.979a4.265 4.265 0 01-.264-.521H10a1 1 0 100-2H8.017a7.36 7.36 0 010-1H10a1 1 0 100-2H8.472a4.265 4.265 0 01.264-.521z" />
          </svg>
          <span className="text-sm text-[hsl(var(--text-secondary))]">
            {t('currentBalance', '当前积分')}:
          </span>
          <span className="text-lg font-bold text-[hsl(var(--warning))]">
            {balance.toLocaleString()}
          </span>
        </div>
      </div>

      {/* Options */}
      <div className="mb-4">
        <p className="text-sm text-[hsl(var(--text-secondary))] mb-2">
          {t('selectDuration', '选择兑换时长')}:
        </p>
        <div className="grid grid-cols-3 gap-2">
          {REDEEM_OPTIONS.map(option => (
            <button
              key={option.days}
              onClick={() => setSelectedDays(option.days)}
              disabled={balance < option.cost}
              className={`p-3 rounded-lg border-2 text-center transition-all ${
                selectedDays === option.days
                  ? 'border-[hsl(var(--accent-primary))] bg-[hsl(var(--accent-primary)/0.1)]'
                  : 'border-[hsl(var(--border-color))] hover:border-[hsl(var(--border-color)/0.5)]'
              } ${balance < option.cost ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}`}
            >
              <p className="text-lg font-bold text-[hsl(var(--text-primary))]">
                {option.days} {t('days', '天')}
              </p>
              <p className="text-sm text-[hsl(var(--warning))]">
                {option.cost} {t('pointsLabel', '积分')}
              </p>
            </button>
          ))}
        </div>
      </div>

      {/* Pro Benefits */}
      <div className="mb-4 p-3 bg-gradient-to-r from-[hsl(var(--accent-primary)/0.1)] to-[hsl(var(--accent-secondary)/0.1)] rounded-lg">
        <p className="text-sm font-medium text-[hsl(var(--text-primary))] mb-2">
          {t('proBenefits', 'Pro 会员权益')}:
        </p>
        <ul className="text-xs text-[hsl(var(--text-secondary))] space-y-1">
          <li className="flex items-center gap-1">
            <svg className="w-3 h-3 text-[hsl(var(--success))]" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
            </svg>
            {t('benefit.unlimitedAI', '无限 AI 对话')}
          </li>
          <li className="flex items-center gap-1">
            <svg className="w-3 h-3 text-[hsl(var(--success))]" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
            </svg>
            {t('benefit.unlimitedProjects', '无限项目')}
          </li>
          <li className="flex items-center gap-1">
            <svg className="w-3 h-3 text-[hsl(var(--success))]" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
            </svg>
            {t('benefit.allFormats', 'TXT 导出')}
          </li>
          <li className="flex items-center gap-1">
            <svg className="w-3 h-3 text-[hsl(var(--success))]" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
            </svg>
            {t('benefit.priority', '优先功能体验')}
          </li>
        </ul>
      </div>

      {/* Error */}
      {redeemMutation.isError && (
        <div className="p-3 bg-[hsl(var(--error)/0.1)] text-[hsl(var(--error))] text-sm rounded-lg">
          {t('redeemFailed', '兑换失败，请稍后重试')}
        </div>
      )}
    </Modal>
  );
}
