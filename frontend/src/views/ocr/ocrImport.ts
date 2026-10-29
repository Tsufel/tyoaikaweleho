import { get } from 'svelte/store';
import { api } from '../../lib/api';
import type { OcrSaveResult } from '../../lib/api/types';
import { alert, openSheet, reportError } from '../../lib/stores/confirm';
import { refreshMonth } from '../../lib/stores/entries';
import { settings, shifts } from '../../lib/stores/settings';
import { importSummary } from './ocrLogic';
import OcrPreviewSheet from './OcrPreviewSheet.svelte';

let busy = false;

/** Import ▸ From image (OCR): pick images, preview/edit the rows, save (v1.3 _import_image). */
export async function openOcrImport(): Promise<void> {
  if (busy) return;
  busy = true;
  try {
    const r = await api.ocr_pick_and_extract();
    if (r.status === 'cancelled') return;
    if (!r.ok) {
      if (r.status === 'error' && r.error.code === 'ocr_failed') {
        const text = r.errors?.length ? r.errors.join('\n') : r.error.message;
        await alert('OCR failed', text, 'error');
      } else if (r.status === 'error' && r.error.code === 'dlc_unavailable') {
        await alert('Image OCR not available', r.error.message || 'Install the Image OCR DLC in Settings ▸ DLC Store.', 'info');
      } else {
        await reportError(r, 'OCR failed');
      }
      return;
    }
    if (!r.candidates.length) {
      await alert('No entries found', 'No timesheet entries could be detected in the image(s).', 'info');
      return;
    }
    const sh = get(shifts);
    const saved = await openSheet<
      { candidates: typeof r.candidates; errors: string[]; shifts: string[]; defaultShift: string },
      OcrSaveResult | null
    >(OcrPreviewSheet, {
      candidates: r.candidates,
      errors: r.errors ?? [],
      shifts: sh,
      defaultShift: get(settings).default_job_shift,
    });
    if (!saved?.ok) return;
    await refreshMonth();
    await alert('Import complete', importSummary(saved, r.errors ?? []), 'success');
  } finally {
    busy = false;
  }
}
