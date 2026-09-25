import unittest

from refresh_jobs import Job, canonical_apply_key, classify_family, classify_type, dedupe, enrich_h1b_history, is_relevant, parse_applyguy, parse_jobright_ba, parse_jobright_pm, parse_new_grad, parse_searchtern, parse_summer, stable_id


class RefreshJobsTests(unittest.TestCase):
    def test_role_classification(self):
        self.assertEqual(classify_family("Associate Product Manager — 2027"), "Product")
        self.assertEqual(classify_family("Product Operations Analyst"), "Product Ops")
        self.assertEqual(classify_family("Growth Operations Associate"), "Growth Ops")

    def test_new_grad_type_includes_rotational_and_entry_level(self):
        self.assertEqual(classify_type("Operations Analyst - Rotational Development Program"), "New Grad")
        self.assertEqual(classify_type("Entry Level Product Manager - 2027"), "New Grad")

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

    def test_jobright_pm_requires_an_explicit_early_career_signal(self):
        source = """
| Company | Job Title | Location | Work Model | Date Posted |
| ----- | --------- | --------- | ---- | ------- |
| **[IBM](https://ibm.example)** | **[Entry Level Product Management 2027](https://example.com/ibm-pm)** | Austin, TX | Hybrid | Sep 23 |
| ↳ | **[Senior Product Manager](https://example.com/senior)** | Austin, TX | Hybrid | Sep 23 |
| **[Example](https://example.com)** | **[Product Demonstrator](https://example.com/demo)** | Remote | Remote | Sep 23 |
| **[Roblox](https://roblox.example)** | **[[2027] Associate Product Manager, Early Career](https://example.com/roblox)** | San Mateo, CA | On Site | Sep 23 |
"""
        jobs = parse_jobright_pm(source)
        self.assertEqual(len(jobs), 2)
        self.assertEqual(jobs[0].company, "IBM")
        self.assertEqual(jobs[0].job_type, "New Grad")
        self.assertEqual(jobs[1].role, "2027 Associate Product Manager, Early Career")

    def test_jobright_business_analyst_keeps_junior_and_graduate_roles(self):
        source = """
| Company | Job Title | Location | Work Model | Date Posted |
| ----- | --------- | --------- | ---- | ------- |
| **[Example](https://example.com)** | **[Junior Business Analyst](https://example.com/junior)** | Remote | Remote | Sep 22 |
| **[Example](https://example.com)** | **[Business Analyst Graduate Programme](https://example.com/grad)** | New York, NY | Hybrid | Sep 21 |
| **[Example](https://example.com)** | **[Business Analyst](https://example.com/general)** | New York, NY | Hybrid | Sep 21 |
"""
        jobs = parse_jobright_ba(source)
        self.assertEqual(len(jobs), 2)
        self.assertTrue(all(job.job_type == "New Grad" for job in jobs))

    def test_searchtern_keeps_us_early_career_roles_and_rejects_refusals(self):
        source = """[
          {"company":"Example","role":"Product Management Intern - Summer 2027","location":"Austin, TX","date":"2026-09-24T01:00:00+00:00","link":"https://example.com/pm?utm_source=x","country_iso":"US","job_type":"internship","is_remote":"false","description":"Students are welcome."},
          {"company":"Blocked","role":"Junior Business Analyst","location":"New York, NY","date":"2026-09-24T01:00:00+00:00","link":"https://example.com/ba","country_iso":"US","job_type":"new_grad","is_remote":"false","description":"We cannot provide visa sponsorship."},
          {"company":"Old","role":"Product Manager Intern - 2026 Start","location":"Seattle, WA","date":"2026-09-24T01:00:00+00:00","link":"https://example.com/old","country_iso":"US","job_type":"internship","is_remote":"false","description":""},
          {"company":"Canada","role":"Associate Product Manager, New Grad","location":"Toronto","date":"2026-09-24T01:00:00+00:00","link":"https://example.com/ca","country_iso":"CA","job_type":"new_grad","is_remote":"false","description":""}
        ]"""
        jobs = parse_searchtern(source)
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0].job_type, "Internship")
        self.assertEqual(jobs[0].source_name, "SearchTern ATS Feed")

    def test_dedupe_ignores_tracking_parameters_on_same_ats_url(self):
        first = Job("1", "Example", "Product Analyst Intern", "NY", "https://example.com/job/1?utm_source=a", "one", "https://one", "section", "Product", "Internship", "Today", "Fresh now", "not-stated", "not provided", "")
        second = Job("2", "Example Inc", "Product Analyst Intern", "New York", "https://example.com/job/1?ref=tracker", "two", "https://two", "section", "Product", "Internship", "Today", "Fresh now", "not-stated", "not provided", "")
        self.assertEqual(canonical_apply_key(first.apply_url), canonical_apply_key(second.apply_url))
        self.assertEqual(len(dedupe([first, second])), 1)

    def test_ids_are_stable(self):
        self.assertEqual(stable_id("A", "B", "C"), stable_id("A", "B", "C"))

    def test_h1b_history_is_company_level_evidence(self):
        job = Job("1", "Example Co", "Product Analyst - 2027", "NY", "https://example.com", "source", "https://source", "section", "Product", "New Grad", "Today", "Fresh now", "not-stated", "source does not state a refusal", "No refusal")
        [result] = enrich_h1b_history([job], {"fiscal_years": [2022, 2023], "employers": {"example": 21}})
        self.assertEqual(result.sponsorship, "history")
        self.assertIn("not a promise", result.sponsorship_evidence)


if __name__ == "__main__":
    unittest.main()
