# evaluate.py
"""
Evaluation script with per-field accuracy
"""
import json
from typing import List, Dict


class Evaluator:
    """Calculate accuracy metrics"""
    
    EVALUATED_FIELDS = [
        'product_line',
        'origin_port_code',
        'origin_port_name',
        'destination_port_code',
        'destination_port_name',
        'incoterm',
        'cargo_weight_kg',
        'cargo_cbm',
        'is_dangerous'
    ]
    
    def compare_field(self, pred_value, true_value, field_name: str) -> bool:
        """Apply comparison rules based on field type"""
        
        # Null comparison - null only equals null
        if pred_value is None and true_value is None:
            return True
        if pred_value is None or true_value is None:
            return False
        
        # String fields - case-insensitive, whitespace trimmed
        if field_name in ['product_line', 'origin_port_code', 'origin_port_name',
                          'destination_port_code', 'destination_port_name', 'incoterm']:
            return str(pred_value).strip().lower() == str(true_value).strip().lower()
        
        # Float fields - exact match after rounding to 2 decimals
        if field_name in ['cargo_weight_kg', 'cargo_cbm']:
            pred_rounded = round(float(pred_value), 2)
            true_rounded = round(float(true_value), 2)
            return pred_rounded == true_rounded
        
        # Boolean field
        if field_name == 'is_dangerous':
            return bool(pred_value) == bool(true_value)
        
        return False
    
    def evaluate(self, predictions: List[dict], ground_truth: List[dict]) -> dict:
        """Calculate accuracy metrics"""
        
        # Create lookup by id
        truth_map = {item['id']: item for item in ground_truth}
        
        field_correct = {field: 0 for field in self.EVALUATED_FIELDS}
        field_total = {field: 0 for field in self.EVALUATED_FIELDS}
        errors = []
        
        for pred in predictions:
            email_id = pred['id']
            if email_id not in truth_map:
                continue
            
            true = truth_map[email_id]
            
            for field in self.EVALUATED_FIELDS:
                field_total[field] += 1
                if self.compare_field(pred.get(field), true.get(field), field):
                    field_correct[field] += 1
                else:
                    errors.append({
                        'id': email_id,
                        'field': field,
                        'predicted': pred.get(field),
                        'expected': true.get(field)
                    })
        
        # Calculate accuracies
        field_accuracies = {
            field: (field_correct[field] / field_total[field] * 100) if field_total[field] > 0 else 0
            for field in self.EVALUATED_FIELDS
        }
        
        total_correct = sum(field_correct.values())
        total_fields = sum(field_total.values())
        overall_accuracy = (total_correct / total_fields * 100) if total_fields > 0 else 0
        
        return {
            'field_accuracies': field_accuracies,
            'overall_accuracy': overall_accuracy,
            'total_correct': total_correct,
            'total_fields': total_fields,
            'errors': errors,
            'field_correct': field_correct,
            'field_total': field_total
        }
    
    def print_results(self, results: dict):
        """Print results in readable format"""
        print("=" * 70)
        print("EVALUATION RESULTS")
        print("=" * 70)
        print(f"\nOVERALL ACCURACY: {results['overall_accuracy']:.2f}%")
        print(f"({results['total_correct']}/{results['total_fields']} fields correct)\n")
        print("-" * 70)
        print("PER-FIELD ACCURACY:")
        print("-" * 70)
        
        for field in self.EVALUATED_FIELDS:
            accuracy = results['field_accuracies'][field]
            correct = results['field_correct'][field]
            total = results['field_total'][field]
            status = "✓" if accuracy == 100.0 else "✗" if accuracy < 80.0 else "~"
            print(f"{status} {field:30s}: {accuracy:6.2f}% ({correct}/{total})")
        
        print("=" * 70)
        
        # Show sample errors
        if results['errors']:
            print(f"\nSample Errors (showing first 10 of {len(results['errors'])}):")
            print("-" * 70)
            for error in results['errors'][:10]:
                print(f"{error['id']:15s} | {error['field']:25s}")
                print(f"  Predicted: {error['predicted']}")
                print(f"  Expected:  {error['expected']}\n")


def main():
    """Main evaluation"""
    
    with open('output.json', 'r', encoding='utf-8') as f:
        predictions = json.load(f)
    
    with open('ground_truth.json', 'r', encoding='utf-8') as f:
        ground_truth = json.load(f)
    
    evaluator = Evaluator()
    results = evaluator.evaluate(predictions, ground_truth)
    evaluator.print_results(results)


if __name__ == "__main__":
    main()