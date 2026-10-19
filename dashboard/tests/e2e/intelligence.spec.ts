import AxeBuilder from '@axe-core/playwright';
import {expect,test} from '@playwright/test';

test('guided analyst calculates an answer, links evidence and refuses unsupported data',async({page})=>{
  await page.goto('/ask');
  await expect(page.getByRole('heading',{level:1})).toHaveText('Ask the evidence.');
  await page.getByRole('button',{name:'Ask the analyst',exact:true}).click();
  await expect(page.getByRole('heading',{name:'What the evidence shows'})).toBeVisible();
  await expect(page.getByRole('region',{name:'Analyst answer'})).toContainText('Diabetes & obesity');
  await page.getByText('1. Growth contributions').click();
  await expect(page.getByRole('link',{name:'Rx Market Pulse snapshot'})).toBeVisible();
  await page.getByLabel('Your question').fill('Show UAE sales');
  await page.getByRole('button',{name:'Ask the analyst',exact:true}).click();
  await expect(page.getByRole('heading',{name:'Outside the available evidence'})).toBeVisible();
});

test('quarterly test results and horizon table are visible',async({page})=>{
  await page.goto('/#outlook');
  await expect(page.locator('#outlook')).toContainText('lost to the baseline');
  await page.getByText('Quarterly observations, forecasts and error by horizon').click();
  await expect(page.getByRole('table',{name:'28 actual quarters and eight future quarters'})).toContainText('2027Q4');
});

test('analyst is accessible on a narrow screen',async({page})=>{
  await page.setViewportSize({width:390,height:844});
  await page.goto('/ask');
  await page.getByRole('button',{name:'Ask the analyst',exact:true}).click();
  await expect(page.getByRole('heading',{name:'What the evidence shows'})).toBeVisible();
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true);
  expect((await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21a','wcag21aa']).analyze()).violations).toEqual([]);
});

test('API rejects cross-origin and invalid input',async({request})=>{
  const origin=await request.post('/api/intelligence',{headers:{origin:'https://unrelated.example'},data:{question:'What is spend?'}});
  expect(origin.status()).toBe(403);
  expect((await request.post('/api/intelligence',{data:{question:'x'}})).status()).toBe(400);
});
