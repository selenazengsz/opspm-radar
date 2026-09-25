import unittest

from refresh_jobs import Job, classify_family, enrich_h1b_history, is_relevant, parse_applyguy, parse_new_grad, parse_summer, stable_id


class RefreshJobsTests(unittest.TestCase):
    def test_role_classification(self):
        self.assertEqual(classify_family("Associate Product Manager — 2027"), "Product")
        self.assertEqual(classify_family("Product Operations Analyst"), "Product Ops")
        self.assertEqual(classify_family("Growth Operations Associate"), "Growth Ops")

    def test_senior_role_is_rejected(self):
        self.assertFalse(is_relevant("Senior Product Manager"))
        self.assertTrue(is_relevant("Product Manager Intern — Summer 2027"))

    def test_zapply_sponsor_signal_is_not_a_guarantee(self):
        markdown = """
<summary><h3>📊 <strong>Business & Operations</strong></h3></summary>
| Company | Role | Location | Posted | Visa | Apply |
|---|---|---|---|---|---|
| **Example Co** | Product Operations Analyst - New Grad | New York, NY | 2h | ✅ Sponsor | [Apply](https://example.com/job) |
"""
        jobs = parse_new_grad(markdown)
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0].sponsorship, "source-signal")
        self.assertIn("not a job-specific guarantee", jobs[0].sponsorship_evidence)

    def test_company_level_signal_is_labeled(self):
        markdown = """
| Company | Role | Location | Posted | Visa | Apply |
|---|---|---|---|---|---|
| **Example Co** | Software Engineer | Remote | 1h | ✅ Sponsor | [Apply](https://example.com/engineering) |
| **Example Co** | Product Operations Analyst - New Grad | New York, NY | 2h |  | [Apply](https://example.com/product) |
"""
        jobs = parse_new_grad(markdown)
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0].sponsorship_scope, "company-level source signal")
        self.assertIn("not proof for this role", jobs[0].sponsorship_evidence)

    def test_closed_summer_role_is_kept_and_labeled(self):
        source = """
<h2>Business / Ops</h2>
<table><tr class="closed"><td>Example Co</td><td>Business Analyst Intern — Summer 2027 closed</td><td>New York, NY</td></tr></table>
"""
        jobs = parse_summer(source)
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0].status, "closed")
        self.assertEqual(jobs[0].job_type, "Internship")

    def test_applyguy_only_keeps_relevant_open_roles(self):
        source = """{
          "jobs": [
            {"company": "Example", "title": "Product Management Intern - Summer 2027", "category": "Product", "location": "Austin, TX", "season": "Summer 2027", "age": "Today", "listingUrl": "https://example.com/pm"},
            {"company": "Example", "title": "Software Engineer Intern", "category": "Software Engineering", "location": "Austin, TX", "age": "Today", "listingUrl": "https://example.com/swe"}
          ]
        }"""
        jobs = parse_applyguy(source)
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0].job_type, "Internship")
        self.assertEqual(jobs[0].posted_bucket, "Fresh now")
        self.assertEqual(jobs[0].apply_url, "https://example.com/pm")

    def test_ids_are_stable(self):
        self.assertEqual(stable_id("A", "B", "C"), stable_id("A", "B", "C"))

    def test_h1b_history_is_company_level_evidence(self):
        job = Job("1", "Example Co", "Product Analyst - 2027", "NY", "https://example.com", "source", "https://source", "section", "Product", "New Grad", "Today", "Fresh now", "not-stated", "source does not state a refusal", "No refusal")
        [result] = enrich_h1b_history([job], {"fiscal_years": [2022, 2023], "employers": {"example": 21}})
        self.assertEqual(result.sponsorship, "history")
        self.assertIn("not a promise", result.sponsorship_evidence)


if __name__ == "__main__":
    unittest.main()
