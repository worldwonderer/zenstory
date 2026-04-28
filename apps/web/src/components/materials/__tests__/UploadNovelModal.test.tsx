import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { UploadNovelModal } from '../UploadNovelModal'

const mockUpload = vi.fn()
const mockValidateFile = vi.fn()
const mockResolveErrorMessage = vi.fn()

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string) =>
      (
        {
          'materials:uploadModal.title': 'Upload novel',
          'materials:uploadModal.errors.noFile': 'Pick a file first',
          'materials:uploadModal.errors.uploadFailed': 'Upload failed',
          'materials:uploadModal.uploading': 'Uploading',
          'materials:uploadModal.upload': 'Upload',
          'materials:uploadModal.clickToSelect': 'Click to select',
          'materials:uploadModal.supportedFormats': 'TXT only',
          'materials:uploadModal.titleLabel': 'Title',
          'materials:uploadModal.titleOptional': 'Optional',
          'materials:uploadModal.titlePlaceholder': 'Novel title',
          'materials:uploadModal.success': 'Upload complete',
          'common:cancel': 'Cancel',
        } as Record<string, string>
      )[key] ?? key,
  }),
}))

vi.mock('../../ui/Modal', () => ({
  default: ({
    open,
    title,
    footer,
    children,
  }: {
    open: boolean
    title: React.ReactNode
    footer: React.ReactNode
    children?: React.ReactNode
  }) => (open ? <div><div>{title}</div>{children}{footer}</div> : null),
}))

vi.mock('../../../lib/materialsApi', () => ({
  materialsApi: {
    upload: (...args: unknown[]) => mockUpload(...args),
  },
}))

vi.mock('../../../lib/materialUploadValidation', () => ({
  validateMaterialUploadFile: (...args: unknown[]) => mockValidateFile(...args),
  resolveMaterialUploadErrorMessage: (...args: unknown[]) => mockResolveErrorMessage(...args),
}))

describe('UploadNovelModal', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockValidateFile.mockResolvedValue(null)
    mockUpload.mockResolvedValue({ id: 'material-1', title: 'Uploaded Novel' })
    mockResolveErrorMessage.mockReturnValue('Upload failed')
  })

  it('shows validation errors for invalid files', async () => {
    mockValidateFile.mockResolvedValueOnce('Invalid file')

    render(<UploadNovelModal open={true} onClose={vi.fn()} onSuccess={vi.fn()} />)

    const input = document.querySelector('input[type="file"]') as HTMLInputElement
    const file = new File(['draft'], 'draft.txt', { type: 'text/plain' })
    fireEvent.change(input, { target: { files: [file] } })

    expect(await screen.findByText('Invalid file')).toBeInTheDocument()
  })

  it('uploads a file, auto-fills the title, and closes after success', async () => {
    const onSuccess = vi.fn()
    const onClose = vi.fn()
    render(<UploadNovelModal open={true} onClose={onClose} onSuccess={onSuccess} />)

    const input = document.querySelector('input[type="file"]') as HTMLInputElement
    const file = new File(['draft'], 'my-novel.txt', { type: 'text/plain' })
    fireEvent.change(input, { target: { files: [file] } })

    await waitFor(() => {
      expect(screen.getByDisplayValue('my-novel')).toBeInTheDocument()
    })

    fireEvent.click(screen.getByRole('button', { name: 'Upload' }))

    expect(mockUpload).toHaveBeenCalledWith(file, 'my-novel')
    expect(await screen.findByText('Upload complete')).toBeInTheDocument()
    await waitFor(() => {
      expect(onSuccess).toHaveBeenCalledWith({ id: 'material-1', title: 'Uploaded Novel' })
      expect(onClose).toHaveBeenCalled()
    }, { timeout: 2000 })
  })

  it('supports drag and drop plus removing the selected file', async () => {
    render(<UploadNovelModal open={true} onClose={vi.fn()} onSuccess={vi.fn()} />)

    const dropZone = screen.getByText('Click to select').closest('div') as HTMLElement
    const file = new File(['draft'], 'drop-novel.txt', { type: 'text/plain' })

    fireEvent.dragOver(dropZone, {
      dataTransfer: { files: [file] },
    })
    fireEvent.drop(dropZone, {
      dataTransfer: { files: [file] },
    })

    await waitFor(() => {
      expect(screen.getByDisplayValue('drop-novel')).toBeInTheDocument()
    })

    fireEvent.click(screen.getByRole('button', { name: '' }))
    expect(screen.getAllByText('TXT only').length).toBeGreaterThan(0)
  })

})
