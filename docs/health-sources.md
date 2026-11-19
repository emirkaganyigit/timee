# Timee içeriklerinin kaynakları

Kaynaklar 19 Kasım 2026 tarihinde kontrol edildi. Uygulama, göz dinlendirme ve nazik hareket hatırlatıcısıdır; görme bozuklukları için tedavi veya kişiye özel egzersiz programı sunmaz.

## Hatırlatma sıklığı

- **Göz: 20 dakika masa başı süresi / doğrulanmış 20 saniye uzağa bakış.** AOA, yaklaşık 6 metre uzaktaki gerçek bir nesneye 20 saniye bakmayı önerir. Otomatik akış her zaman bu davranışın bir çeşidini içerir: genel uzak nesne, pencerenin ötesi veya odanın en uzak sabit noktası. Buna AAO'nun doğal göz kırpma rehberini ya da Moorfields NHS'in gözleri kısa süre nazikçe kapatma önerisini gösteren 10 saniyelik destekleyici bir adım eşlik eder. İki adım toplam 30 saniyedir ve ilk adım bittiğinde sıradaki adım kendiliğinden başlar.
- **Hareket: 60 dakika masa başı süresi / tek nazik hareket.** HSE sık ve kısa molaları önerir ve 50–60 dakikalık kesintisiz ekran çalışmasından sonra 5–10 dakikalık mola örneği verir; evrensel tek bir aralık belirtmez. Timee'nin 60 dakikalık varsayılanı, daha az bölünme isteğini de gözeten ürün seçimidir. Her uyarı, kaynaklı havuzdan yalnızca bir hareket sunar. Kısa bir hareketin tek başına HSE'nin bütün ekran dışı mola örneğine eşdeğer olduğu iddia edilmez.
- **Daha sık hareket seçeneği: 30 dakika.** Newcastle NHS iş gününde 30 dakikada bir pozisyon değiştirmeyi önerir. Bu, daha sık hareket etmeyi isteyenler için kaynaklı bir seçenektir.

Varsayılan düzende aynı masa başı periyodunun 20. ve 40. dakikalarında 30 saniyelik göz akışı; 60. dakikada ise göz ve hareket seçenekleri aynı pencerede alt alta sunulur. Kullanıcı hangisini önce yapmak istediğini seçebilir ve ikisini ayrı ayrı atlayabilir.

Hatırlatma kadansı çalışma kronometresinden bağımsız **masa başı süresini** ölçer. Çalışma sayacını durdurmak göz veya hareket kadansını durdurmaz ve sıfırlamaz. Kullanıcı gerçekten masasından ayrıldığında ayrı masa kontrolünü durdurur; bu sırada iki kadans da donar. Geri dönmek, açık kadansı kaldığı yerden sürdürür. Bu ayrım, kullanıcının çalışmayı durdurup masada kaldığı bir arayı yanlışlıkla hareket molası saymaz.

Hareket uyarısındaki **10 dakika ertele**, hareket yapıldığı iddiasında bulunmadan yalnızca bir sonraki uyarıyı on dakika öteler. **Molada hareket ettim** seçeneği hareket kadansını normal tam aralığına döndürür. Atlamak, mevcut öneriyi tamamlanmış mola olarak kaydetmeden kapatır. Bunlar kullanıcı kontrolü için zamanlama tercihleridir; kaynaklarda doğrulanmış klinik protokoller değildir.

Uyarı açıldığında çalınan iki yumuşak ton, uygulama için yerel olarak üretilmiş bir PCM WAV dosyasıdır. Sağlık müdahalesi değildir; kullanıcı ekrana bakmıyorken uyarıyı fark edebilsin diye sunulur ve ayarlardan kapatılabilir.

## Egzersizlerin kaynakla eşleşmesi

| İçerik | Dayanak |
| --- | --- |
| 20 saniye yaklaşık 6 metre uzağa bakma | AOA 20-20-20 önerisi |
| Pencere/oda içindeki uzak sabit noktaya bakma | AOA uzak bakış ilkesi ve OSHA'nın düzenli olarak uzak nesnelere odaklanma rehberi |
| Doğal göz kırpmayı hatırlama | AAO ve OSHA; belirli tekrar sayısı veya 10 saniyelik klinik doz iddiası yok |
| Gözleri sıkmadan kısa süre kapatma | Moorfields NHS; 10 saniyelik uygulama süresi Timee sunumudur |
| Ayağa kalkma / kısa yürüyüş / duruş değiştirme | HSE mola rehberi |
| 5 yavaş otur–kalk; 5 destekli topuk kaldırma | NHS Strength exercises |
| Göğüs açma: 5–10 saniye, 5 tekrar | NHS Sitting exercises |
| Omuzları 3 kez öne ve 3 kez geriye çevirme | Newcastle NHS |
| Elleri hafifçe yumruk yapıp parmakları açma: 3 tekrar | Newcastle NHS |

`content.py` içindeki `duration`, animasyon ve rehber ekranı için yaklaşık süredir. Uzağa bakışın kaynakta belirtilen 20 saniyesi dışında bunlar doğrulanmış klinik egzersiz dozları değildir. Otomatik sıra değişimi, çeşit rotasyonu, masa başı zamanlaması ve erteleme süresi de doğrulanmış bir tedavi ya da egzersiz programı değildir. Kaynakta yer alan tekrar/tutma önerileri `reps` alanında ayrıca belirtilir. Sabit, kaymayan, tekerleksiz sandalye ve rahat hareket aralığı kullanılmalı; ağrı olursa hareket bırakılmalıdır. Kullanıcı her öneriyi atlayabilmelidir.

## Kanıtın sınırı

Doğru ifade **“AOA, AAO, OSHA ve NHS rehberlerine dayalı”**dır. Her hareketin her kişide etkili olduğu veya 20-20-20 sayılarının en iyi düzen olduğu iddia edilmez. Mola vermek ve uzağa bakmak kurumların pratik önerileridir; tam sıklık ve sürenin etkisine ilişkin çalışmalar aynı sonucu vermemiştir.

Timee genel kullanıcılara sekiz çizme, hızlı sağ-sol/yukarı-aşağı bakış, kalem yaklaştırma, konverjans çalışması, “göz yogası”, masaj/baskı veya ekrandaki noktayı izleme hareketleri sunmaz. AAO sıradan “göz egzersizlerinin” görmeyi keskinleştirdiğinin kanıtlanmadığını; NHS ortoptik/konverjans çalışmalarının ise değerlendirme sonrası belirli durumlar için verildiğini belirtir. Uygulama miyopiyi düzeltme, göz kaslarını güçlendirme veya görmeyi iyileştirme iddiası taşımaz.

## Kaynak bağlantıları

1. [American Optometric Association — Computer vision syndrome / 20-20-20](https://www.aoa.org/healthy-eyes/eye-and-vision-conditions/computer-vision-syndrome/20-20-20-rule?sso=y)
2. [American Academy of Ophthalmology — Computers, Digital Devices, and Eye Strain](https://www.aao.org/eye-health/glasses-contacts/computer-usage)
3. [OSHA — Computer workstation monitor guidance](https://www.osha.gov/etools/computer-workstations/components/monitors)
4. [Moorfields NHS — 10 steps for digital eye-strain relief](https://www.moorfields.nhs.uk/private/about-moorfields-private/blog-articles/10-steps-for-digital-eye-strain-relief)
5. [Health and Safety Executive — Work routine and breaks](https://www.hse.gov.uk/msd/dse/work-routine.htm)
6. [NHS — Strength exercises](https://www.nhs.uk/live-well/exercise/strength-exercises/)
7. [NHS — Sitting exercises](https://www.nhs.uk/live-well/exercise/sitting-exercises/)
8. [Newcastle Hospitals NHS — 1 minute body check](https://www.newcastle-hospitals.nhs.uk/services/newcastle-occupational-health-service/information-for-staff/physiotherapy/self-help-leaflets/1-minute-body-check/)
9. [AAO — Vision training is not proven to make vision sharper](https://www.aao.org/eye-health/tips-prevention/vision-training-not-proven-to-make-vision-sharper)
10. [University Hospitals Plymouth NHS — Orthoptic eye exercises](https://www.plymouthhospitals.nhs.uk/display-pil/pil-eye-exercises-6845)
11. [20-20-20 Rule: Are These Numbers Justified? — 2023 araştırması, PubMed](https://pubmed.ncbi.nlm.nih.gov/36473088/)
12. [The effects of breaks on digital eye strain, dry eye and binocular vision: Testing the 20-20-20 rule — PubMed](https://pubmed.ncbi.nlm.nih.gov/35963776/)
