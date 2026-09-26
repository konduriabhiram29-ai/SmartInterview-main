import asyncio
from playwright.async_api import async_playwright

async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()
        
        # Helper for console logs
        page.on('console', lambda msg: print(f'Console: {msg.text}') if msg.type == 'error' else None)
        # Handle confirm dialogs
        page.on('dialog', lambda dialog: dialog.accept())
        
        try:
            print('Navigating to register...')
            await page.goto('http://localhost:5174/register')
            await page.fill('input[type="text"]', 'Test E2E User 5')
            await page.fill('input[type="email"]', 'teste2e5@example.com')
            await page.fill('input[type="password"]', 'Password123!')
            await page.fill('input[id="confirmPassword"]', 'Password123!')
            await page.click('button:has-text("Create Account")')
            
            try:
                await page.wait_for_url('http://localhost:5174/dashboard', timeout=5000)
                print('Registered successfully.')
            except Exception:
                print('Already registered, logging in...')
                await page.goto('http://localhost:5174/login')
                await page.fill('input[type="email"]', 'teste2e5@example.com')
                await page.fill('input[type="password"]', 'Password123!')
                await page.click('button:has-text("Sign In")')
                await page.wait_for_url('http://localhost:5174/dashboard')
            
            # RESUME MODE
            print('Testing Resume Mode...')
            await page.goto('http://localhost:5174/resume')
            
            print('Setting resume file input...')
            inputs = page.locator('input[type="file"]')
            await inputs.nth(0).set_input_files('dummy_resume.pdf')
            
            print('Waiting for resume parsing...')
            await page.wait_for_selector('text=Candidate:', timeout=20000)
            print('Resume uploaded.')
            
            print('Setting JD file input...')
            await inputs.nth(1).set_input_files('dummy_jd.pdf')
            await page.wait_for_selector('text=Continue to Setup', timeout=20000)
            
            # Continue to setup
            print('Clicking continue to setup...')
            await page.click('button:has-text("Continue to Setup")')
            await page.wait_for_url('http://localhost:5174/setup')
            
            # Start Interview
            print('Clicking start interview in setup...')
            await page.click('button:has-text("Start Interview")')
            
            # Wait for interview page
            print('Waiting for interview page...')
            await page.wait_for_selector('.chat-message, textarea', timeout=30000)
            print('Resume Interview Started.')
            
            for i in range(3):
                # Type an answer
                await page.fill('textarea', f'This is test answer {i+1} for resume mode.')
                await page.click('button:has-text("Submit Answer")')
                print(f'Sent answer {i+1}')
                await page.wait_for_timeout(4000)
                
            print('Ending Resume Interview...')
            await page.click('button:has-text("Finish Interview")')
            await page.wait_for_selector('text=Interview Results', timeout=30000)
            print('Resume Interview Finished successfully.')
            
            # SYLLABUS MODE
            print('Testing Syllabus Mode...')
            await page.goto('http://localhost:5174/syllabus')
            
            await page.set_input_files('input[type="file"]', 'dummy_syllabus.pdf')
            await page.click('button:has-text("Analyze & Extract Topics")')
            
            await page.wait_for_selector('text=Material Processed', timeout=30000)
            print('Syllabus uploaded and analyzed.')
            
            # Select all topics
            await page.wait_for_selector('button:has-text("Select All")')
            await page.wait_for_timeout(1000)
            await page.click('button:has-text("Select All")')
            
            # Start Syllabus Interview
            await page.click('button:has-text("Start Exam Preparation")')
            await page.wait_for_selector('textarea', timeout=30000)
            print('Syllabus Interview Started.')
            
            for i in range(3):
                await page.fill('textarea', f'This is test answer {i+1} for syllabus mode.')
                await page.click('button:has-text("Submit Answer")')
                print(f'Sent answer {i+1}')
                await page.wait_for_timeout(4000)
                
            print('Ending Syllabus Interview...')
            await page.click('button:has-text("Finish Interview")')
            await page.wait_for_selector('text=Interview Results', timeout=30000)
            print('Syllabus Interview Finished successfully.')
            
        except Exception as e:
            print(f'Test failed: {e}')
        
        await browser.close()

asyncio.run(run())
