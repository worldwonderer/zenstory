import React, { createContext, useContext, useState, useCallback } from 'react';
import type { ReactNode } from 'react';

export interface SkillTriggerContextType {
  /** 待插入的触发词 */
  pendingTrigger: string | null;
  /** 插入触发词到聊天输入框 */
  insertTrigger: (trigger: string) => void;
  /** 消费（清除）待插入的触发词 */
  consumeTrigger: () => void;
}

const SkillTriggerContext = createContext<SkillTriggerContextType | undefined>(undefined);

export const SkillTriggerProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [pendingTrigger, setPendingTrigger] = useState<string | null>(null);

  const insertTrigger = useCallback((trigger: string) => {
    setPendingTrigger(trigger);
  }, []);

  const consumeTrigger = useCallback(() => {
    setPendingTrigger(null);
  }, []);

  return (
    <SkillTriggerContext.Provider value={{ pendingTrigger, insertTrigger, consumeTrigger }}>
      {children}
    </SkillTriggerContext.Provider>
  );
};

// eslint-disable-next-line react-refresh/only-export-components
export const useSkillTrigger = (): SkillTriggerContextType => {
  const context = useContext(SkillTriggerContext);
  if (context === undefined) {
    throw new Error('useSkillTrigger must be used within a SkillTriggerProvider');
  }
  return context;
};
