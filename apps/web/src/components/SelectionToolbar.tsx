import React, { useEffect, useRef } from 'react';
import { createPortal } from 'react-dom';
import { Quote } from 'lucide-react';
import { useTranslation } from 'react-i18next';

interface SelectionToolbarProps {
  /** 选中的文本 */
  text: string;
  /** 工具栏位置 */
  position: { x: number; y: number };
  /** 添加引用回调 */
  onAdd: () => void;
  /** 关闭回调 */
  onClose: () => void;
}

export const SelectionToolbar: React.FC<SelectionToolbarProps> = ({
  text,
  position,
  onAdd,
  onClose,
}) => {
  const { t } = useTranslation('chat');
  const toolbarRef = useRef<HTMLDivElement>(null);

  // 处理点击外部关闭
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (toolbarRef.current && !toolbarRef.current.contains(e.target as Node)) {
        onClose();
      }
    };

    // 延迟添加事件监听，避免立即触发
    const timer = setTimeout(() => {
      document.addEventListener('mousedown', handleClickOutside);
    }, 0);

    return () => {
      clearTimeout(timer);
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [onClose]);

  // 处理 Escape 键关闭
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose();
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [onClose]);

  const handleAdd = () => {
    onAdd();
    onClose();
  };

  // 如果没有选中文本，不渲染
  if (!text) return null;

  return createPortal(
    <div
      ref={toolbarRef}
      className="fixed z-50 animate-in fade-in zoom-in-95 duration-150"
      style={{
        left: position.x,
        top: position.y,
        transform: 'translate(-50%, -100%)',
      }}
    >
      <div className="flex items-center gap-1 px-2 py-1.5 bg-[hsl(var(--bg-secondary))] border border-[hsl(var(--border-primary))] rounded-lg shadow-lg">
        <button
          onClick={handleAdd}
          className="flex items-center gap-1.5 px-2 py-1 text-xs text-[hsl(var(--text-secondary))] hover:text-[hsl(var(--text-primary))] hover:bg-[hsl(var(--bg-tertiary))] rounded transition-colors"
          title={t('input.addToContext')}
        >
          <Quote size={14} />
          <span>{t('input.addToContext')}</span>
        </button>
      </div>
      {/* 小三角指向选中文本 */}
      <div
        className="absolute left-1/2 -translate-x-1/2 w-2 h-2 bg-[hsl(var(--bg-secondary))] border-r border-b border-[hsl(var(--border-primary))] rotate-45"
        style={{ bottom: -5 }}
      />
    </div>,
    document.body
  );
};
