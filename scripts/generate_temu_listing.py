import argparse
import asyncio
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.config import get_settings
from core.database import async_session_factory, dispose_engine
from integrations.excel.listing_validation_writer import ListingValidationReportError
from integrations.temu.template_adapter import TemuTemplateError
from services.listing_generation_service import ListingGenerationError, ListingGenerationService


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate and validate deterministic Temu PBN listing data."
    )
    parser.add_argument("--design-batch", required=True, type=Path)
    parser.add_argument("--template", required=True, type=Path)
    parser.add_argument("--mapping", type=Path, help="Reviewed mapping for the real Temu template")
    parser.add_argument("--supplier", default="LINGDIAN")
    parser.add_argument("--output-dir", type=Path, default=Path("outputs/listings"))
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--commit", action="store_true")
    return parser.parse_args()


async def run() -> int:
    args = parse_args()
    service = ListingGenerationService(get_settings(), async_session_factory, PROJECT_ROOT)
    try:
        result = await service.run(
            design_batch_path=args.design_batch,
            template_path=args.template,
            mapping_path=args.mapping,
            supplier_code=args.supplier,
            output_root=args.output_dir,
            commit=args.commit,
        )
    except (
        ListingGenerationError,
        ListingValidationReportError,
        TemuTemplateError,
        ValueError,
    ) as exc:
        print(f"Listing generation failed: {exc}", file=sys.stderr)
        return 4
    finally:
        await dispose_engine()

    manifest = result["manifest"]
    summary = result["payload"]["summary"]
    print("Temu Listing Commit" if args.commit else "Temu Listing Dry Run")
    print(f"Batch: {manifest['batch_id']}")
    print(f"Products: {summary['products']} ({summary['valid_products']} valid)")
    print(f"SKUs: {summary['skus']} ({summary['valid_skus']} valid)")
    print(f"Missing images: {summary['missing_images']}")
    print(f"Missing factory costs: {summary['missing_factory_cost']}")
    print(f"Template ready: {summary['template_ready']}")
    print(f"Validation report: {manifest['validation_report']}")
    print(f"Manifest: {result['manifest_path']}")
    if args.commit:
        print(f"Temu workbook: {manifest['temu_batch_listing']}")
    else:
        print("Formal Temu upload workbook NOT created in dry-run mode.")
    return (
        0 if not any(issue["severity"] == "ERROR" for issue in result["payload"]["issues"]) else 2
    )


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run()))
