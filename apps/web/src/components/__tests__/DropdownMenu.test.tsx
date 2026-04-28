import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import type { LucideIcon } from 'lucide-react'
import { DropdownMenu } from '../ui/DropdownMenu'

const TestIcon: LucideIcon = (props) => <svg {...props} data-testid="menu-item-icon" />

describe('DropdownMenu', () => {
  it('opens with ArrowDown and focuses first menu item', async () => {
    render(
      <DropdownMenu
        triggerTitle="More actions"
        items={[
          { icon: TestIcon, label: 'First action', onClick: vi.fn() },
          { icon: TestIcon, label: 'Second action', onClick: vi.fn() },
        ]}
      />
    )

    const trigger = screen.getByRole('button', { name: 'More actions' })
    fireEvent.keyDown(trigger, { key: 'ArrowDown' })

    const firstItem = await screen.findByRole('menuitem', { name: 'First action' })
    await waitFor(() => {
      expect(firstItem).toHaveFocus()
    })
  })

  it('supports Arrow navigation and Escape closes back to trigger', async () => {
    render(
      <DropdownMenu
        triggerTitle="More actions"
        items={[
          { icon: TestIcon, label: 'First action', onClick: vi.fn() },
          { icon: TestIcon, label: 'Second action', onClick: vi.fn() },
        ]}
      />
    )

    const trigger = screen.getByRole('button', { name: 'More actions' })
    fireEvent.click(trigger)

    const menu = await screen.findByRole('menu')
    const firstItem = screen.getByRole('menuitem', { name: 'First action' })
    const secondItem = screen.getByRole('menuitem', { name: 'Second action' })

    fireEvent.keyDown(menu, { key: 'ArrowDown' })
    await waitFor(() => {
      expect(firstItem).toHaveFocus()
    })

    fireEvent.keyDown(menu, { key: 'ArrowDown' })
    await waitFor(() => {
      expect(secondItem).toHaveFocus()
    })

    fireEvent.keyDown(menu, { key: 'Escape' })

    await waitFor(() => {
      expect(screen.queryByRole('menu')).not.toBeInTheDocument()
      expect(trigger).toHaveFocus()
    })
  })
})
